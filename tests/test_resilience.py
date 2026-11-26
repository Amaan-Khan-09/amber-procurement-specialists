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
    for k in ("NVIDIA_API_KEY", "HF_TOKEN"):
        monkeypatch.delenv(k, raising=False)
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
    for k in ("NVIDIA_API_KEY", "HF_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert LLM(provider="groq").fallbacks == ["cerebras"]


def test_nvidia_and_hugging_face_host_the_same_model_and_join_the_chain(monkeypatch):
    monkeypatch.delenv("AMBER_FALLBACK", raising=False)
    for k in ("OPENROUTER_API_KEY", "CEREBRAS_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k in ("GROQ_API_KEY", "NVIDIA_API_KEY", "HF_TOKEN"):
        monkeypatch.setenv(k, "x")
    llm = LLM(provider="groq")
    assert llm.fallbacks == ["nvidia", "huggingface"]
    assert LLM(provider="nvidia").model == LLM(provider="huggingface").model == "openai/gpt-oss-120b"


def test_a_host_that_rejects_a_setting_is_asked_again_with_plain_settings(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "x")
    llm = LLM(provider="nvidia")
    sent = []

    def fake_post(url, headers, body):
        sent.append(dict(body))
        if "reasoning_effort" in body or "response_format" in body:
            raise LLMError("nvidia HTTP 400: unsupported parameter")
        return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.json("s", "u") == {"ok": True}
    assert "reasoning_effort" not in sent[-1] and "response_format" not in sent[-1]


def test_account_ids_and_keys_never_reach_a_saved_message():
    from amber.llm import LLMError
    msg = ("groq HTTP 429: Rate limit reached in organization `org_" + "0a1b2c3d4e5f6g7h8i9j` key gsk_" + "A" * 40
           + " and AIza" + "B" * 35)
    out = str(LLMError(msg))
    assert "org_" not in out and "gsk_" not in out and "AIza" not in out and "Rate limit reached" in out
