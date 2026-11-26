"""One JSON-in/JSON-out interface over Groq (cloud), Gemini (long documents) and Ollama (offline).

Every call is metered (tokens, cost, calls) so each tool can report the cost per run the rules ask for.
The model only ever *extracts*; decisions are made in code (see checks.py).
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

from . import budget
from .schema import ModelUsage

load_dotenv()

# USD per 1M tokens (input, output). Cost is reported at paid-tier list prices even when a free
# tier was used, so the number is honest for a real customer. Verify before submitting.
PRICES = {
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "gemini-3.8-flash": (0.75, 3.75),  # intro rate to 2026-12-31 (third-party reports; check ai.google.dev/pricing)
}

DEFAULTS = {
    "groq": os.getenv("AMBER_GROQ_MODEL", "openai/gpt-oss-120b"),
    "gemini": os.getenv("AMBER_GEMINI_MODEL", "gemini-3.8-flash"),
    "ollama": os.getenv("AMBER_OLLAMA_MODEL", "qwen3:8b"),
}

# Other hosts of the same open-weight model through an OpenAI-compatible API. Each is used only if its key is set.
# Free tiers by default, so they may serve as automatic fallbacks (unlike a paid provider, which is opt-in).
COMPAT = {
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key": "OPENROUTER_API_KEY",
                   "model": os.getenv("AMBER_OPENROUTER_MODEL", "openai/gpt-oss-120b:free"),
                   "extra": {"reasoning": {"effort": "low"}}},
    "cerebras": {"base": "https://api.cerebras.ai/v1", "key": "CEREBRAS_API_KEY",
                 "model": os.getenv("AMBER_CEREBRAS_MODEL", "gpt-oss-120b"),
                 "extra": {"reasoning_effort": "low"}},
    # NVIDIA hosted API (build.nvidia.com, free trial key)
    "nvidia": {"base": "https://integrate.api.nvidia.com/v1", "key": "NVIDIA_API_KEY",
               "model": os.getenv("AMBER_NVIDIA_MODEL", "openai/gpt-oss-120b"),
               "extra": {"reasoning_effort": "low"}},
    # Hugging Face Inference Providers router (free monthly credits; token needs "Make calls to Inference Providers")
    "huggingface": {"base": "https://router.huggingface.co/v1", "key": "HF_TOKEN",
                    "model": os.getenv("AMBER_HF_MODEL", "openai/gpt-oss-120b"),
                    "extra": {"reasoning_effort": "low"}},
}
for _name, _cfg in COMPAT.items():
    DEFAULTS[_name] = _cfg["model"]
PRICES.setdefault("openai/gpt-oss-120b:free", (0.0, 0.0))  # OpenRouter free variant
# Cerebras free-trial credit: reported at the same list price as gpt-oss-120b elsewhere, so cost per run stays honest
PRICES.setdefault("gpt-oss-120b", PRICES["openai/gpt-oss-120b"])

FREE_FALLBACKS = "openrouter,cerebras,nvidia,huggingface"  # tried in this order after the primary, only if their keys are set


_PRIVATE = re.compile(r"\b(org|proj|project|user|key|acct)([_-])[A-Za-z0-9]{8,}|\b(gsk|sk|hf|nvapi)([_-])[A-Za-z0-9_-]{16,}"
                      r"|\bAIza[A-Za-z0-9_-]{20,}")


def scrub(text: str) -> str:
    """Remove account identifiers and API keys from a provider's message: errors are stored inside results."""
    return _PRIVATE.sub("(hidden)", text)


class LLMError(RuntimeError):
    def __init__(self, message: str = ""):
        super().__init__(scrub(str(message)))


@dataclass
class Meter:
    usage: dict[str, ModelUsage] = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)  # one entry per model call: what for, which model, cost, outcome

    def add(self, provider: str, model: str, tin: int, tout: int) -> None:
        self._last = (tin, tout)
        u = self.usage.setdefault(model, ModelUsage(name=model, provider=provider))
        u.tokens_in += tin
        u.tokens_out += tout
        u.calls += 1
        pin, pout = PRICES.get(model, (0.0, 0.0))
        u.cost_usd = round(u.tokens_in / 1e6 * pin + u.tokens_out / 1e6 * pout, 6)
        if provider == "gemini":  # paid: every call goes on the persistent ledger
            budget.record(tin / 1e6 * pin + tout / 1e6 * pout)

    def models(self) -> list[ModelUsage]:
        return list(self.usage.values())


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise LLMError(f"no JSON in model reply: {text[:200]!r}")
    obj = json.loads(text[start:])
    return obj if isinstance(obj, dict) else {"items": obj}


def _has_key(provider: str) -> bool:
    if provider == "groq":
        return bool(os.getenv("GROQ_API_KEY"))
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    if provider in COMPAT:
        return bool(os.getenv(COMPAT[provider]["key"]))
    return provider == "ollama"


class LLM:
    def __init__(self, provider: str | None = None, model: str | None = None, meter: Meter | None = None,
                 timeout: float = 120.0):
        self.provider = provider or os.getenv("AMBER_PROVIDER", "groq")
        if self.provider not in DEFAULTS:
            raise LLMError(f"unknown provider {self.provider}")
        self.model = model or DEFAULTS[self.provider]
        self.meter = meter or Meter()
        # a laptop CPU needs minutes per call: local models get a long timeout instead of dying at 120 s
        self.client = httpx.Client(timeout=max(timeout, 1800.0) if self.provider == "ollama" else timeout)
        # When the primary provider is unavailable (rate limit longer than we wait, outage), calls move to
        # the next provider that has a key. Usage is metered under the model that actually answered.
        # Default: free hosts of the same model (if their keys are set); never a paid provider unless opted in with
        # AMBER_FALLBACK=...,gemini (still capped). The local model is never a silent fallback for a cloud run.
        chain = [p.strip() for p in os.getenv("AMBER_FALLBACK", FREE_FALLBACKS).split(",") if p.strip()]
        self.fallbacks = [p for p in chain if p != self.provider and p in DEFAULTS and _has_key(p)]
        self.switched: list[str] = []

    @property
    def local(self) -> bool:
        return self.provider == "ollama"

    def json(self, system: str, user: str, max_tokens: int = 4000, schema: dict | None = None,
             purpose: str = "") -> dict:
        """Ask for a JSON object. One repair retry if the reply is not valid JSON; provider fallback on outage.
        `schema` (JSON Schema) constrains decoding where the provider supports it (Ollama), which keeps
        small local models on format. Every call is logged in meter.steps with its purpose."""
        self._schema = schema
        t0, before = time.time(), (sum(u.tokens_in for u in self.meter.usage.values()),
                                   sum(u.tokens_out for u in self.meter.usage.values()))
        step = {"step": len(self.meter.steps) + 1, "purpose": purpose or "model call"}

        def log(ok: bool, error: str = ""):
            tin = sum(u.tokens_in for u in self.meter.usage.values()) - before[0]
            tout = sum(u.tokens_out for u in self.meter.usage.values()) - before[1]
            step.update(provider=self.provider, model=self.model, tokens_in=tin, tokens_out=tout,
                        ms=int((time.time() - t0) * 1000), ok=ok, **({"error": error[:160]} if error else {}))
            self.meter.steps.append(step)

        while True:
            try:
                out = self._json_once(system, user, max_tokens)
                log(True)
                return out
            except LLMError as e:
                if "invalid JSON" in str(e) or not self.fallbacks:
                    log(False, str(e))
                    raise
                nxt = self.fallbacks.pop(0)
                self.switched.append(f"{self.provider}->{nxt}: {str(e)[:120]}")
                self.provider, self.model = nxt, DEFAULTS[nxt]

    def _json_once(self, system: str, user: str, max_tokens: int) -> dict:
        last = None
        for attempt in range(2):
            prompt = user if attempt == 0 else user + "\n\nYour previous reply was not valid JSON. Reply with JSON only."
            text = getattr(self, f"_{self.provider}")(system, prompt, max_tokens)
            try:
                return _parse_json(text)
            except (json.JSONDecodeError, LLMError) as e:
                last = e
        raise LLMError(f"invalid JSON after retry: {last}")

    # ---- providers -------------------------------------------------------------------------
    def _post(self, url: str, headers: dict, body: dict) -> dict:
        if "generativelanguage.googleapis.com" in url:
            budget.check()  # refuse before sending once the spending cap is reached
        max_wait = float(os.getenv("AMBER_MAX_WAIT", "65"))  # free tiers refill per minute
        r = None
        for attempt in range(4):
            try:
                r = self.client.post(url, headers=headers, json=body)
            except httpx.TransportError as e:  # dropped connection, timeout: retry, then give up cleanly
                if attempt == 3:
                    raise LLMError(f"{self.provider} network error: {e}") from e
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                wait = float(r.headers.get("retry-after", 2 * (attempt + 1))) + 2
                if wait > max_wait:
                    break
                time.sleep(wait)
                continue
            break
        if r.status_code >= 400:
            raise LLMError(f"{self.provider} HTTP {r.status_code}: {scrub(r.text)[:300]}")
        return r.json()

    def _groq(self, system: str, user: str, max_tokens: int) -> str:
        key = os.getenv("GROQ_API_KEY") or ""
        if not key:
            raise LLMError("GROQ_API_KEY not set")
        body = {"model": self.model, "temperature": 0, "max_completion_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = "low"
        url, hdr = "https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {key}"}
        try:
            j = self._post(url, hdr, body)
        except LLMError as e:
            # Groq's strict JSON mode sometimes rejects a reply ("Failed to generate JSON", HTTP 400). Ask again
            # without strict mode; _parse_json still validates the reply, so nothing unchecked gets through.
            if "HTTP 400" not in str(e) or "json" not in str(e).lower():
                raise
            body.pop("response_format", None)
            j = self._post(url, hdr, body)
        u = j.get("usage", {})
        self.meter.add("groq", self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        return j["choices"][0]["message"]["content"] or ""

    def _compat(self, system: str, user: str, max_tokens: int) -> str:
        """Any OpenAI-compatible host of the same model (OpenRouter, Cerebras, NVIDIA, Hugging Face)."""
        cfg = COMPAT[self.provider]
        key = os.getenv(cfg["key"]) or ""
        if not key:
            raise LLMError(f"{cfg['key']} not set")
        body = {"model": self.model, "temperature": 0, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], **cfg["extra"]}
        url = f"{cfg['base']}/chat/completions"
        hdr = {"Authorization": f"Bearer {key}", "X-Title": "amber-procurement-specialists"}
        try:
            j = self._post(url, hdr, body)
        except LLMError as e:  # some hosts reject strict JSON mode or a reasoning setting: ask again with plain settings
            if "HTTP 400" not in str(e):
                raise
            body.pop("response_format", None)
            try:
                j = self._post(url, hdr, body)
            except LLMError as e2:
                if "HTTP 400" not in str(e2) or not cfg["extra"]:
                    raise
                for k in cfg["extra"]:
                    body.pop(k, None)
                j = self._post(url, hdr, body)
        u = j.get("usage") or {}
        self.meter.add(self.provider, self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        return (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""

    _openrouter = _compat
    _cerebras = _compat
    _nvidia = _compat
    _huggingface = _compat

    def _gemini(self, system: str, user: str, max_tokens: int) -> str:
        key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        if not key:
            raise LLMError("GEMINI_API_KEY / GOOGLE_API_KEY not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens,
                                     "responseMimeType": "application/json",
                                     "thinkingConfig": {"thinkingBudget": 0}}}
        j = self._post(url, {"x-goog-api-key": key}, body)
        u = j.get("usageMetadata", {})
        self.meter.add("gemini", self.model, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0))
        parts = j["candidates"][0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    def _ollama(self, system: str, user: str, max_tokens: int) -> str:
        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        # Small context window: the KV cache for 16k tokens alone is ~2.4 GB on a 4B model, which pushed a 16 GB
        # laptop into swapping. Prompts for local runs are kept under ~3k tokens instead (see submittal._limits).
        body = {"model": self.model, "stream": False, "think": False, "keep_alive": "30m",
                "format": getattr(self, "_schema", None) or "json",
                "options": {"temperature": 0, "num_predict": max_tokens,
                            "num_ctx": int(os.getenv("AMBER_OLLAMA_CTX", "4096"))},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        j = self._post(f"{host}/api/chat", {}, body)
        self.meter.add("ollama", self.model, j.get("prompt_eval_count", 0), j.get("eval_count", 0))
        return j["message"]["content"]
