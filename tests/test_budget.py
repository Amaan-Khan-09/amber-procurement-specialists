"""The Gemini spending cap: calls are refused once the ledger reaches the cap; Groq is never affected."""
import pytest

from amber import budget
from amber.llm import LLM, LLMError, Meter


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBER_BUDGET_FILE", str(tmp_path / "spend.json"))
    monkeypatch.setenv("AMBER_GEMINI_BUDGET_USD", "0.10")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    return tmp_path / "spend.json"


def test_gemini_usage_is_recorded_on_the_ledger(ledger):
    Meter().add("gemini", "gemini-3.8-flash", 1_000_000, 0)  # $0.75 at list price
    assert budget.spent_usd() == pytest.approx(0.75)


def test_groq_usage_is_never_charged_to_the_gemini_ledger(ledger):
    Meter().add("groq", "openai/gpt-oss-120b", 1_000_000, 1_000_000)
    assert budget.spent_usd() == 0.0


def test_call_is_refused_before_sending_once_cap_reached(ledger, monkeypatch):
    budget.record(0.10)
    llm = LLM(provider="gemini")
    sent = []
    monkeypatch.setattr(llm.client, "post", lambda *a, **k: sent.append(1))
    with pytest.raises(LLMError, match="budget reached"):
        llm.json("s", "u")
    assert not sent  # nothing left the machine


def test_no_automatic_paid_fallback_by_default(monkeypatch):
    monkeypatch.delenv("AMBER_FALLBACK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert "gemini" not in LLM(provider="groq").fallbacks  # free hosts may be fallbacks; paid Gemini never automatically
