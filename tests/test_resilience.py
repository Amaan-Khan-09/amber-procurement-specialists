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


def test_every_model_call_is_logged_with_its_purpose(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    llm = LLM(provider="groq")

    def fake(*a, **k):
        llm.meter.add("groq", llm.model, 100, 20)
        return '{"ok": true}'

    monkeypatch.setattr(llm, "_groq", fake)
    llm.json("s", "u", purpose="read bid B1")
    monkeypatch.setattr(llm, "_groq", lambda *a, **k: (_ for _ in ()).throw(LLMError("down")))
    try:
        llm.json("s", "u", purpose="read bid B2")
    except LLMError:
        pass
    s1, s2 = llm.meter.steps
    assert s1["purpose"] == "read bid B1" and s1["ok"] and s1["tokens_in"] == 100 and s1["tokens_out"] == 20
    assert s2["purpose"] == "read bid B2" and not s2["ok"] and "down" in s2["error"]


def test_free_hosts_of_the_same_model_take_over_in_order(monkeypatch):
    monkeypatch.delenv("AMBER_FALLBACK", raising=False)
    for k in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "CEREBRAS_API_KEY"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    llm = LLM(provider="groq")
    assert llm.fallbacks == ["openrouter", "cerebras"]  # free hosts only; paid Gemini is never automatic
    sent = []

    def fake_post(url, headers, body):
        sent.append((url, body["model"]))
        if "groq" in url:
            raise LLMError("groq HTTP 429: tokens per day")
        return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {"prompt_tokens": 50, "completion_tokens": 5}}

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.json("s", "u", purpose="read bid B1") == {"ok": True}
    assert sent[-1] == ("https://openrouter.ai/api/v1/chat/completions", "openai/gpt-oss-120b:free")
    assert llm.meter.steps[-1]["provider"] == "openrouter" and llm.meter.steps[-1]["ok"]
    assert "groq->openrouter" in llm.switched[0]


def test_a_host_without_a_key_is_skipped(monkeypatch):
    monkeypatch.delenv("AMBER_FALLBACK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("CEREBRAS_API_KEY", "x")
    assert LLM(provider="groq").fallbacks == ["cerebras"]
