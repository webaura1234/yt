from pathlib import Path

from moviepy.editor import ColorClip

from utils.video import (
    _SECONDARY_VIDEO_SEARCH_TERMS,
    _extract_keywords,
    _generate_placeholder_secondary_clip,
    _pick_valid_cached_video,
    _validate_video_file,
)


def _make_clip(dest: Path, width: int, height: int, duration: float = 1.0) -> None:
    clip = ColorClip(size=(width, height), color=(10, 10, 10), duration=duration).set_fps(24)
    clip.write_videofile(str(dest), codec="libx264", audio=False, logger=None)


def test_extract_keywords_uses_provided_search_terms():
    terms = ["pyramids", "pharaoh", "desert"]
    assert set(_extract_keywords(terms)) == set(terms)


def test_extract_keywords_falls_back_to_generic_list_when_empty():
    assert set(_extract_keywords([])) == set(_SECONDARY_VIDEO_SEARCH_TERMS)


def test_extract_keywords_falls_back_to_generic_list_when_none():
    assert set(_extract_keywords(None)) == set(_SECONDARY_VIDEO_SEARCH_TERMS)


def test_extract_keywords_strips_blank_entries():
    assert _extract_keywords(["  ", "", "pyramids"]) == ["pyramids"]


def test_generate_placeholder_secondary_clip_is_landscape_and_valid(tmp_path: Path):
    dest = tmp_path / "placeholder.mp4"
    _generate_placeholder_secondary_clip(dest, duration=1.0)

    assert dest.exists()
    assert _validate_video_file(dest, min_duration=0.5, min_width=100)


def test_validate_video_file_rejects_empty_file(tmp_path: Path):
    bogus = tmp_path / "empty.mp4"
    bogus.write_bytes(b"")
    assert _validate_video_file(bogus) is False


def test_validate_video_file_rejects_portrait_orientation(tmp_path: Path):
    dest = tmp_path / "portrait.mp4"
    _make_clip(dest, width=240, height=426)
    assert _validate_video_file(dest, min_duration=0.5, min_width=100) is False


def test_validate_video_file_accepts_landscape_orientation(tmp_path: Path):
    dest = tmp_path / "landscape.mp4"
    _make_clip(dest, width=426, height=240)
    assert _validate_video_file(dest, min_duration=0.5, min_width=100) is True


def test_validate_video_file_rejects_low_resolution(tmp_path: Path):
    dest = tmp_path / "tiny.mp4"
    _make_clip(dest, width=100, height=60)
    assert _validate_video_file(dest, min_duration=0.5, min_width=640) is False


def test_pick_valid_cached_video_prunes_corrupt_file(tmp_path: Path):
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"")

    assert _pick_valid_cached_video(tmp_path) is None
    assert not corrupt.exists()


def test_pick_valid_cached_video_returns_the_valid_file(tmp_path: Path):
    valid = tmp_path / "valid.mp4"
    _make_clip(valid, width=640, height=360)  # default min_width is 640

    assert _pick_valid_cached_video(tmp_path) == valid


def test_pick_valid_cached_video_returns_none_when_empty(tmp_path: Path):
    assert _pick_valid_cached_video(tmp_path) is None
