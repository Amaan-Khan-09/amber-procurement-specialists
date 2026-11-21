"""Provider fallback and graceful degradation: an outage changes who answers, never what is claimed."""
from amber import checks
from amber.docs import Document, Page
from amber.llm import LLM, LLMError
from amber.schema import Verdict
from amber.submittal import _decide_condition


def test_falls_back_to_next_provider_and_records_it(monkeypatch):
    monkeypatch.setenv("AMBER_FALLBACK", "gemini")  # paid fallback is opt-in
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    llm = LLM(provider="groq")

    def down(*a, **k):
        raise LLMError("groq HTTP 429: tokens per day")

    monkeypatch.setattr(llm, "_groq", down)
    monkeypatch.setattr(llm, "_gemini", lambda *a, **k: '{"ok": true}')
    assert llm.json("s", "u") == {"ok": True}
    assert llm.provider == "gemini" and llm.switched and "groq->gemini" in llm.switched[0]


def test_no_fallback_left_raises(monkeypatch):
    monkeypatch.setenv("AMBER_FALLBACK", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    llm = LLM(provider="groq")
    monkeypatch.setattr(llm, "_groq", lambda *a, **k: (_ for _ in ()).throw(LLMError("down")))
    try:
        llm.json("s", "u")
        raise AssertionError("should have raised")
    except LLMError:
        pass


def test_unchecked_condition_is_never_reported_as_missing():
    doc = Document("d", "d.pdf", pages=[Page(1, "text " * 20)])
    cond = {"cid": "R01a", "kind": "numeric", "op": ">=", "value": 2000, "unit": "kW"}
    d, cite, conf = _decide_condition(cond, {"cid": "R01a", "not_checked": "model unavailable"}, doc)
    assert d.verdict == Verdict.unclear and conf == 0.0 and cite is None
    assert checks.decide(cond, None).verdict == Verdict.missing  # only a real 'not stated' is missing


def test_groq_outage_does_not_silently_use_paid_gemini(monkeypatch):
    monkeypatch.delenv("AMBER_FALLBACK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    llm = LLM(provider="groq")
    called = []
    monkeypatch.setattr(llm, "_groq", lambda *a, **k: (_ for _ in ()).throw(LLMError("groq HTTP 429")))
    monkeypatch.setattr(llm, "_gemini", lambda *a, **k: called.append(1) or "{}")
    try:
        llm.json("s", "u")
    except LLMError:
        pass
    assert not called
