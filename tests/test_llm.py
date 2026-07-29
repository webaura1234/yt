import pytest

import utils.llm as llm


def test_generate_uses_gemini_by_default(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(llm, "_openai_client", object())

    monkeypatch.setattr(llm, "_call_gemini", lambda *a, **k: "gemini-response")

    def fail_openai(*args, **kwargs):
        raise AssertionError("OpenAI should not be called when Gemini succeeds")

    monkeypatch.setattr(llm, "_call_openai", fail_openai)

    assert llm._generate("system prompt", "user content") == "gemini-response"


def test_generate_falls_back_to_openai_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(llm, "_openai_client", object())  # truthy sentinel: fallback configured

    def failing_gemini(*args, **kwargs):
        raise Exception("gemini boom")

    monkeypatch.setattr(llm, "_call_gemini", failing_gemini)
    monkeypatch.setattr(llm, "_call_openai", lambda *a, **k: "openai-response")

    assert llm._generate("system prompt", "user content") == "openai-response"


def test_generate_raises_when_gemini_fails_and_no_openai_fallback(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(llm, "_openai_client", None)

    def failing_gemini(*args, **kwargs):
        raise Exception("gemini boom")

    monkeypatch.setattr(llm, "_call_gemini", failing_gemini)

    with pytest.raises(Exception, match="gemini boom"):
        llm._generate("system prompt", "user content")


def test_generate_uses_openai_when_gemini_not_configured(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "_openai_client", object())

    def fail_gemini(*args, **kwargs):
        raise AssertionError("Gemini should not be called when GEMINI_API_KEY is unset")

    monkeypatch.setattr(llm, "_call_gemini", fail_gemini)
    monkeypatch.setattr(llm, "_call_openai", lambda *a, **k: "openai-response")

    assert llm._generate("system prompt", "user content") == "openai-response"


def test_generate_raises_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm, "_openai_client", None)

    with pytest.raises(Exception, match="No LLM provider configured"):
        llm._generate("system prompt", "user content")


def test_call_openai_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(llm, "_openai_client", None)

    with pytest.raises(Exception, match="OpenAI fallback unavailable"):
        llm._call_openai("prompt", None, False)


def test_call_gemini_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    calls = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise Exception("transient network error")
        return FakeResponse()

    monkeypatch.setattr(llm.requests, "post", fake_post)

    result = llm._call_gemini("sys", "user", False, retries=3)

    assert result == "ok"
    assert calls["n"] == 2


def test_call_gemini_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    def always_fail(*args, **kwargs):
        raise Exception("network down")

    monkeypatch.setattr(llm.requests, "post", always_fail)

    with pytest.raises(Exception, match="Gemini text generation failed after 2 attempts"):
        llm._call_gemini("sys", "user", False, retries=2)
