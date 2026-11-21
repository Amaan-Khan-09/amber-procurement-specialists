"""Hard spending cap for paid APIs (Gemini). A persistent ledger survives across runs and processes.

  AMBER_GEMINI_BUDGET_USD   total cap in USD (default 1.50). Once spent >= cap, every Gemini call is
                            refused before it is sent; callers degrade to 'not checked' or use Groq.
  AMBER_BUDGET_FILE         ledger path (default .cache/gemini_spend.json)

Spend is estimated from token counts at list price (see llm.PRICES), so it is a close upper-ish estimate of
the real bill, not an invoice. Check the real figure in Google AI Studio / Cloud Billing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _path() -> Path:
    return Path(os.getenv("AMBER_BUDGET_FILE", ROOT / ".cache" / "gemini_spend.json"))


def cap_usd() -> float:
    return float(os.getenv("AMBER_GEMINI_BUDGET_USD", "1.50"))


def _read() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"spent_usd": 0.0, "calls": 0}


def spent_usd() -> float:
    return float(_read().get("spent_usd", 0.0))


def remaining_usd() -> float:
    return max(0.0, cap_usd() - spent_usd())


def check() -> None:
    """Raise before a paid call if the cap is reached."""
    from .llm import LLMError  # local import: llm imports this module
    if spent_usd() >= cap_usd():
        raise LLMError(f"gemini budget reached (${spent_usd():.2f} of ${cap_usd():.2f}); call not sent")


def record(cost_usd: float) -> None:
    d = _read()
    d["spent_usd"] = round(float(d.get("spent_usd", 0.0)) + cost_usd, 6)
    d["calls"] = int(d.get("calls", 0)) + 1
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1), encoding="utf-8")
