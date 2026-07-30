import base64
from pathlib import Path

import pytest
import requests

import utils.audio as audio
from utils.audio import (
    _backfill_known_attribution,
    _FALLBACK_TRACK_URLS,
    _generate_placeholder_song,
    _pick_valid_cached_song,
    _validate_audio_file,
    generate_voiceover,
)
from utils.downloads import attribution_credit_line


def test_generate_placeholder_song_is_valid(tmp_path: Path):
    dest = tmp_path / "silence.wav"
    _generate_placeholder_song(dest, duration=5.0)

    assert dest.exists()
    assert _validate_audio_file(dest, min_duration=3.0)


def test_validate_audio_file_rejects_empty_file(tmp_path: Path):
    bogus = tmp_path / "empty.mp3"
    bogus.write_bytes(b"")

    assert _validate_audio_file(bogus) is False


def test_validate_audio_file_rejects_too_short_clip(tmp_path: Path):
    dest = tmp_path / "tooshort.wav"
    _generate_placeholder_song(dest, duration=1.0)

    assert _validate_audio_file(dest, min_duration=3.0) is False


def test_backfill_known_attribution_matches_by_filename(tmp_path: Path):
    known_name = next(iter(_FALLBACK_TRACK_URLS))
    media = tmp_path / f"{known_name}.mp3"
    media.write_bytes(b"fake audio bytes")

    assert attribution_credit_line(media) is None

    _backfill_known_attribution(media)

    credit = attribution_credit_line(media)
    assert credit is not None
    assert known_name in credit
    assert "CC BY 3.0" in credit


def test_backfill_known_attribution_noop_for_unknown_filename(tmp_path: Path):
    media = tmp_path / "some-random-untracked-file.mp3"
    media.write_bytes(b"fake audio bytes")

    _backfill_known_attribution(media)

    assert attribution_credit_line(media) is None


def test_pick_valid_cached_song_prunes_corrupt_file(tmp_path: Path):
    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"")

    assert _pick_valid_cached_song(tmp_path) is None
    assert not corrupt.exists()  # pruned as invalid


def test_pick_valid_cached_song_returns_the_valid_file(tmp_path: Path):
    valid = tmp_path / "valid.wav"
    _generate_placeholder_song(valid, duration=5.0)

    assert _pick_valid_cached_song(tmp_path) == valid


def test_pick_valid_cached_song_returns_none_when_empty(tmp_path: Path):
    assert _pick_valid_cached_song(tmp_path) is None


def _fake_success_response():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            audio_b64 = base64.b64encode(b"fake wav bytes").decode()
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": audio_b64,
                                        "mimeType": "audio/wav",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    return FakeResponse()


def _fake_quota_response(retry_delay: str):
    class FakeResponse:
        status_code = 429

        def raise_for_status(self):
            error = requests.exceptions.HTTPError("429 quota exceeded")
            error.response = self
            raise error

        def json(self):
            return {
                "error": {
                    "message": "You exceeded your current quota",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": retry_delay,
                        }
                    ],
                }
            }

    return FakeResponse()


def test_generate_voiceover_retries_after_short_quota_delay(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audio, "TEMP_PATH", tmp_path)
    monkeypatch.setattr(audio, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(audio.time, "sleep", lambda s: None)

    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _fake_quota_response("5s") if calls["n"] == 1 else _fake_success_response()

    monkeypatch.setattr(audio.requests, "post", fake_post)

    path = generate_voiceover("hello world")

    assert calls["n"] == 2
    assert path.exists()


def test_generate_voiceover_fails_fast_on_long_quota_delay(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audio, "TEMP_PATH", tmp_path)
    monkeypatch.setattr(audio, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(audio.time, "sleep", lambda s: None)

    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _fake_quota_response("3600s")  # an hour - not worth blocking on

    monkeypatch.setattr(audio.requests, "post", fake_post)

    with pytest.raises(Exception, match="Gemini TTS quota exceeded"):
        generate_voiceover("hello world")

    assert calls["n"] == 1  # failed fast instead of burning retries on a hopeless wait


def test_generate_voiceover_retries_transient_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audio, "TEMP_PATH", tmp_path)
    monkeypatch.setattr(audio, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(audio.time, "sleep", lambda s: None)

    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise Exception("transient network error")
        return _fake_success_response()

    monkeypatch.setattr(audio.requests, "post", fake_post)

    path = generate_voiceover("hello world")

    assert calls["n"] == 2
    assert path.exists()
