"""OCR for scanned (image-only) pages, using a vision model. Results are cached per page by docs.load.

The OCR text is only ever used as *evidence to verify quotes against*, and every citation from an
OCR'd page is marked ocr=true with lower confidence, because transcription can be wrong.
"""
from __future__ import annotations

import base64
import os

import pymupdf

from .llm import LLM, LLMError, Meter

PROMPT = ("Transcribe ALL text on this scanned document page exactly as printed: same words, numbers, units "
          "and symbols. Keep each table row on one line with cells separated by two spaces. Do not summarise, "
          "translate, correct or add anything. If the page has no text, reply with an empty string.")

VISION = {"groq": os.getenv("AMBER_GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
          "gemini": os.getenv("AMBER_GEMINI_MODEL", "gemini-2.5-flash")}


def _shrink(png: bytes, max_side: int = 1600) -> bytes:
    pix = pymupdf.Pixmap(png)
    scale = max_side / max(pix.width, pix.height)
    if scale >= 1:
        return png
    doc = pymupdf.open(stream=png, filetype="png")
    return doc[0].get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png")


class VisionOCR:
    """callable(png_bytes) -> text. Prefers Gemini when a key is set, else Groq."""

    def __init__(self, provider: str | None = None, meter: Meter | None = None):
        has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        self.provider = provider or ("gemini" if has_gemini and os.getenv("AMBER_OCR", "") != "groq" else "groq")
        self.llm = LLM(provider=self.provider, model=VISION[self.provider], meter=meter)

    def __call__(self, png: bytes) -> str:
        try:
            return self._read(png, self.provider)
        except (LLMError, KeyError, IndexError):
            if self.provider == "groq":
                raise
            self.provider = "groq"  # e.g. Gemini key invalid: fall back for the rest of the run
            self.llm = LLM(provider="groq", model=VISION["groq"], meter=self.llm.meter)
            return self._read(png, "groq")

    def _read(self, png: bytes, provider: str) -> str:
        img = base64.b64encode(_shrink(png)).decode()
        if provider == "gemini":
            body = {"contents": [{"role": "user", "parts": [{"text": PROMPT},
                                                            {"inline_data": {"mime_type": "image/png", "data": img}}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 4000, "thinkingConfig": {"thinkingBudget": 0}}}
            key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
            j = self.llm._post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.llm.model}:generateContent",
                               {"x-goog-api-key": key}, body)
            u = j.get("usageMetadata", {})
            self.llm.meter.add("gemini", self.llm.model, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0))
            parts = j["candidates"][0]["content"].get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()
        key = os.getenv("GROQ_API_KEY") or ""
        if not key:
            raise LLMError("GROQ_API_KEY not set")
        body = {"model": self.llm.model, "temperature": 0, "max_completion_tokens": 2500,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}]}]}
        if "qwen3" in self.llm.model:
            body["reasoning_effort"] = "none"
        j = self.llm._post("https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {key}"}, body)
        u = j.get("usage", {})
        self.llm.meter.add("groq", self.llm.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        text = j["choices"][0]["message"]["content"] or ""
        import re
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
