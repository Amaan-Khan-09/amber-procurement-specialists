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

from .schema import ModelUsage

load_dotenv()

# USD per 1M tokens (input, output). Cost is reported at paid-tier list prices even when a free
# tier was used, so the number is honest for a real customer. Verify before submitting.
PRICES = {
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "gemini-2.5-flash": (0.30, 2.50),
}

DEFAULTS = {
    "groq": os.getenv("AMBER_GROQ_MODEL", "openai/gpt-oss-120b"),
    "gemini": os.getenv("AMBER_GEMINI_MODEL", "gemini-2.5-flash"),
    "ollama": os.getenv("AMBER_OLLAMA_MODEL", "qwen3:4b"),
}


class LLMError(RuntimeError):
    pass


@dataclass
class Meter:
    usage: dict[str, ModelUsage] = field(default_factory=dict)

    def add(self, provider: str, model: str, tin: int, tout: int) -> None:
        u = self.usage.setdefault(model, ModelUsage(name=model, provider=provider))
        u.tokens_in += tin
        u.tokens_out += tout
        u.calls += 1
        pin, pout = PRICES.get(model, (0.0, 0.0))
        u.cost_usd = round(u.tokens_in / 1e6 * pin + u.tokens_out / 1e6 * pout, 6)

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


class LLM:
    def __init__(self, provider: str | None = None, model: str | None = None, meter: Meter | None = None,
                 timeout: float = 120.0):
        self.provider = provider or os.getenv("AMBER_PROVIDER", "groq")
        if self.provider not in DEFAULTS:
            raise LLMError(f"unknown provider {self.provider}")
        self.model = model or DEFAULTS[self.provider]
        self.meter = meter or Meter()
        self.client = httpx.Client(timeout=timeout)

    def json(self, system: str, user: str, max_tokens: int = 4000) -> dict:
        """Ask for a JSON object. One repair retry if the reply is not valid JSON."""
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
        max_wait = float(os.getenv("AMBER_MAX_WAIT", "65"))  # free tiers refill per minute
        for attempt in range(4):
            r = self.client.post(url, headers=headers, json=body)
            if r.status_code in (429, 500, 502, 503) and attempt < 3:
                wait = float(r.headers.get("retry-after", 2 * (attempt + 1))) + 2
                if wait > max_wait:
                    break
                time.sleep(wait)
                continue
            break
        if r.status_code >= 400:
            raise LLMError(f"{self.provider} HTTP {r.status_code}: {r.text[:300]}")
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
        j = self._post("https://api.groq.com/openai/v1/chat/completions",
                       {"Authorization": f"Bearer {key}"}, body)
        u = j.get("usage", {})
        self.meter.add("groq", self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        return j["choices"][0]["message"]["content"] or ""

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
        body = {"model": self.model, "stream": False, "format": "json", "think": False,
                "options": {"temperature": 0, "num_predict": max_tokens, "num_ctx": 16384},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        j = self._post(f"{host}/api/chat", {}, body)
        self.meter.add("ollama", self.model, j.get("prompt_eval_count", 0), j.get("eval_count", 0))
        return j["message"]["content"]
