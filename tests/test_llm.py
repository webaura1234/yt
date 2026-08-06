import json

import pytest

import utils.llm as llm
from utils.characters import ART_STYLE, cast_for_topic
from utils.safety import UnsafeContentError


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


def test_get_topic_uses_llm_specialization(monkeypatch):
    monkeypatch.setattr(
        llm, "_generate", lambda *a, **k: json.dumps({"topic": "specific angle"})
    )

    assert llm.get_topic() == "specific angle"


def test_get_topic_falls_back_to_raw_category_on_llm_failure(monkeypatch):
    def failing_generate(*args, **kwargs):
        raise Exception("gemini boom")

    monkeypatch.setattr(llm, "_generate", failing_generate)

    from config import POSSIBLE_TOPICS

    assert llm.get_topic() in POSSIBLE_TOPICS


def test_get_most_engaging_titles_converts_1_based_indices_correctly(monkeypatch):
    titles = ["First title", "Second title"]
    monkeypatch.setattr(
        llm, "_generate", lambda *a, **k: json.dumps({"most_engaging_titles": [1, 2]})
    )

    result = llm.get_most_engaging_titles(titles, n=1)

    # Regression test: the prompt numbers 1-based, so index 1 must map to
    # titles[0] ("First title"), not titles[1] ("Second title").
    assert result == ["First title"]


def test_get_most_engaging_titles_falls_back_when_llm_returns_out_of_range_indices(monkeypatch):
    titles = ["Only title"]
    monkeypatch.setattr(
        llm, "_generate", lambda *a, **k: json.dumps({"most_engaging_titles": [0, 99]})
    )

    result = llm.get_most_engaging_titles(titles, n=1)

    assert result == ["Only title"]


def test_get_visual_prompts_requests_one_prompt_per_sentence(monkeypatch):
    script = "This is the hook. Here is the reveal. This is the impact."

    captured = {}

    def fake_generate(prompt, json_mode=False):
        captured["prompt"] = prompt
        return json.dumps({"visual_prompts": ["scene one", "scene two", "scene three"]})

    monkeypatch.setattr(llm, "_generate", fake_generate)

    result = llm.get_visual_prompts("title", script)

    assert len(result) == 3
    assert result[0].startswith("scene one")
    assert "EXACTLY 3" in captured["prompt"]


def test_get_visual_prompts_appends_house_art_style_to_every_prompt(monkeypatch):
    # The style must be on every frame verbatim or the artwork drifts between
    # sentences, so it is appended in code rather than requested from the model.
    monkeypatch.setattr(
        llm,
        "_generate",
        lambda *a, **k: json.dumps({"visual_prompts": ["a", "b"]}),
    )

    result = llm.get_visual_prompts("title", "One. Two.")

    assert all(ART_STYLE in prompt for prompt in result)


def test_get_visual_prompts_tells_the_illustrator_how_the_cast_looks(monkeypatch):
    captured = {}

    def fake_generate(prompt, json_mode=False):
        captured["prompt"] = prompt
        return json.dumps({"visual_prompts": ["only scene"]})

    monkeypatch.setattr(llm, "_generate", fake_generate)
    llm.get_visual_prompts("title", "One sentence.", topic="Space, Planets and Stars")

    cast = cast_for_topic("Space, Planets and Stars")
    for character in cast:
        assert character.appearance in captured["prompt"]


def test_get_visual_prompts_returns_empty_list_for_empty_script(monkeypatch):
    assert llm.get_visual_prompts("title", "") == []


def test_derive_query_falls_back_to_a_scene_for_telugu_sentences():
    # Telugu narration has no Latin words to scrape, and feeding Telugu to an
    # English image model produces nothing usable - so the fallback must be a
    # real describable scene, not an empty string.
    derived = llm._derive_query_from_sentence("సూర్యుడు చాలా వేడిగా ఉంటాడు.")

    assert len(derived) > 20
    assert derived.isascii()


def test_generate_safe_regenerates_when_the_safety_gate_rejects(monkeypatch):
    calls = []

    def fake_generate(prompt, user_content=None, json_mode=False):
        calls.append(1)
        # First answer smuggles in violence; the retry is clean.
        return "the king was killed" if len(calls) == 1 else "a happy sunny day"

    monkeypatch.setattr(llm, "_generate", fake_generate)

    assert llm._generate_safe("prompt", where="script") == "a happy sunny day"
    assert len(calls) == 2


def test_generate_safe_raises_when_every_attempt_is_unsafe(monkeypatch):
    monkeypatch.setattr(llm, "_generate", lambda *a, **k: "a scary ghost story")

    with pytest.raises(UnsafeContentError):
        llm._generate_safe("prompt", where="script", attempts=2)


def test_get_topic_discards_an_unsafe_topic_and_uses_the_category(monkeypatch):
    from config import POSSIBLE_TOPICS

    monkeypatch.setattr(
        llm, "_generate", lambda *a, **k: json.dumps({"topic": "why soldiers die in war"})
    )

    assert llm.get_topic() in POSSIBLE_TOPICS


def test_align_terms_to_sentence_count_truncates_extra_terms():
    sentences = ["One.", "Two."]
    terms = ["a", "b", "c", "d"]

    assert llm._align_terms_to_sentence_count(terms, sentences) == ["a", "b"]


def test_align_terms_to_sentence_count_pads_missing_terms_by_repeating_last():
    sentences = ["One.", "Two.", "Three."]
    terms = ["a"]

    assert llm._align_terms_to_sentence_count(terms, sentences) == ["a", "a", "a"]


def test_align_terms_to_sentence_count_derives_from_sentence_when_zero_terms():
    sentences = ["A shocking discovery happened today.", "Nobody saw it coming."]

    result = llm._align_terms_to_sentence_count([], sentences)

    assert len(result) == 2
    assert result[0] == "A shocking discovery happened today"
    assert result[1] == "Nobody saw it coming"
