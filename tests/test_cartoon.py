import io

import pytest
from PIL import Image

import utils.cartoon as cartoon


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Point the artwork cache at a temp dir so tests never touch the real one."""
    monkeypatch.setattr(cartoon, "CARTOON_CACHE_PATH", tmp_path)


def _png_bytes(width: int, height: int, color=(120, 40, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_generated_image_is_cropped_to_the_shorts_canvas(monkeypatch):
    # The model is asked for portrait but does not reliably obey; a letterboxed
    # frame inside a 9:16 canvas looks broken, so it must be cover-cropped.
    monkeypatch.setattr(cartoon, "_request_image", lambda prompt: _png_bytes(1920, 1080))

    path = cartoon.generate_scene_image("a wide landscape")

    assert Image.open(path).size == (cartoon.SCENE_WIDTH, cartoon.SCENE_HEIGHT)


def test_a_scene_still_gets_artwork_when_generation_fails(monkeypatch):
    # A children's video that fails to render is worse than one with plainer
    # artwork, so an unavailable image model must not abort the video.
    monkeypatch.setattr(cartoon, "_request_image", lambda prompt: None)

    path = cartoon.generate_scene_image("anything at all")

    assert path.exists()
    assert Image.open(path).size == (cartoon.SCENE_WIDTH, cartoon.SCENE_HEIGHT)


def test_undecodable_image_data_falls_back_rather_than_raising(monkeypatch):
    monkeypatch.setattr(cartoon, "_request_image", lambda prompt: b"not an image")

    path = cartoon.generate_scene_image("a broken response")

    assert path.exists()


def test_fallback_cards_differ_between_scenes(monkeypatch):
    # If every fallback were the same flat colour the whole video would collapse
    # to one frame, which no child would watch.
    monkeypatch.setattr(cartoon, "_request_image", lambda prompt: None)

    paths = cartoon.generate_scene_images(["scene one", "scene two", "scene three"])

    assert len({p.read_bytes() for p in paths}) == 3


def test_artwork_is_cached_so_a_repeated_prompt_is_not_paid_for_twice(monkeypatch):
    calls = []

    def counting_request(prompt):
        calls.append(prompt)
        return _png_bytes(896, 1600)

    monkeypatch.setattr(cartoon, "_request_image", counting_request)

    first = cartoon.generate_scene_image("a repeated scene")
    second = cartoon.generate_scene_image("a repeated scene")

    assert first == second
    assert len(calls) == 1, "cache miss: the image model was called twice"


def test_one_image_is_returned_per_prompt_in_order(monkeypatch):
    monkeypatch.setattr(cartoon, "_request_image", lambda prompt: None)

    prompts = ["a", "b", "c", "d"]
    paths = cartoon.generate_scene_images(prompts)

    assert len(paths) == len(prompts)
    assert all(p.exists() for p in paths)


def test_request_image_returns_none_without_an_api_key(monkeypatch):
    monkeypatch.setattr(cartoon, "GEMINI_API_KEY", "")

    assert cartoon._request_image("a prompt") is None
