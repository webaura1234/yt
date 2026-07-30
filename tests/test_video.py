from pathlib import Path

import pytest
from moviepy.editor import ColorClip, CompositeVideoClip, VideoFileClip

import utils.video as video_module
from utils.video import (
    _SECONDARY_VIDEO_SEARCH_TERMS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    LOWER_THIRD_HEIGHT,
    _apply_shot_effect,
    _assign_effect,
    _compute_crop_box,
    _extract_keywords,
    _generate_placeholder_secondary_clip,
    _pick_subclip_start,
    _pick_valid_cached_video,
    _split_sentence_into_subshots,
    _validate_video_file,
    combine_videos,
    create_karaoke_subtitles,
    create_lower_third_backdrop,
    subject_aware_crop,
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


def test_create_lower_third_backdrop_is_transparent_at_top_and_darker_at_bottom():
    backdrop = create_lower_third_backdrop(duration=1.0, max_opacity=0.65)

    assert backdrop.size == (CANVAS_WIDTH, LOWER_THIRD_HEIGHT)

    mask_frame = backdrop.mask.get_frame(0)
    assert mask_frame[0, 0] == 0
    assert mask_frame[-1, 0] > mask_frame[0, 0]
    assert mask_frame[-1, 0] == pytest.approx(0.65, abs=0.05)


def test_create_karaoke_subtitles_renders_in_lower_third_not_top_half():
    words = [{"text": "HI", "start": 0.0, "end": 0.5}]
    clips = create_karaoke_subtitles(words, video_duration=0.5)
    assert len(clips) == 1

    bg = ColorClip(size=(CANVAS_WIDTH, CANVAS_HEIGHT), color=(0, 0, 0), duration=0.5)
    composite = CompositeVideoClip([bg, clips[0]])
    frame = composite.get_frame(0.1)

    top_half = frame[: CANVAS_HEIGHT // 2]
    bottom_third = frame[CANVAS_HEIGHT - LOWER_THIRD_HEIGHT :]

    assert not (top_half != 0).any()
    assert (bottom_third != 0).any()


def test_compute_crop_box_defaults_to_center_when_no_subject():
    # Landscape source, portrait target - width is the limiting dimension.
    crop_w, crop_h, x_center, y_center = _compute_crop_box(1920, 1080, 1080, 1920)
    assert crop_h == 1080
    assert crop_w == pytest.approx(1080 * 1080 / 1920)
    assert x_center == 1920 / 2
    assert y_center == 1080 / 2


def test_compute_crop_box_handles_portrait_source():
    # Portrait source already taller than the target ratio - height is limiting.
    crop_w, crop_h, x_center, y_center = _compute_crop_box(1080, 2400, 1080, 1920)
    assert crop_w == 1080
    assert crop_h == pytest.approx(1080 * 1920 / 1080)
    assert x_center == 1080 / 2


def test_compute_crop_box_centers_on_subject_and_clamps_near_edge():
    # Subject near the right edge of a wide source - crop box must stay in bounds.
    crop_w, crop_h, x_center, y_center = _compute_crop_box(
        1920, 1080, 1080, 1920, subject_center=(1900, 1000)
    )
    assert x_center + crop_w / 2 <= 1920
    assert x_center - crop_w / 2 >= 0
    assert y_center + crop_h / 2 <= 1080
    assert y_center - crop_h / 2 >= 0


def test_subject_aware_crop_falls_back_to_center_crop_when_no_face_detected(monkeypatch):
    monkeypatch.setattr(video_module, "_sample_subject_center", lambda clip: None)

    clip = ColorClip(size=(640, 360), color=(50, 100, 150), duration=1.0)
    result = subject_aware_crop(clip, target_width=CANVAS_WIDTH, target_height=CANVAS_HEIGHT)

    assert result.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_subject_aware_crop_uses_detected_subject_center(monkeypatch):
    # Fake a subject near the left edge of a wide source clip.
    monkeypatch.setattr(video_module, "_sample_subject_center", lambda clip: (50, 180))

    clip = ColorClip(size=(640, 360), color=(50, 100, 150), duration=1.0)
    result = subject_aware_crop(clip, target_width=CANVAS_WIDTH, target_height=CANVAS_HEIGHT)

    assert result.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


def test_assign_effect_is_deterministic_and_cycles_without_immediate_repeat():
    effects = [_assign_effect(i) for i in range(10)]
    # Same input -> same output, every time.
    assert [_assign_effect(i) for i in range(10)] == effects
    # No two consecutive shots share an effect.
    assert all(effects[i] != effects[i + 1] for i in range(len(effects) - 1))


def test_apply_shot_effect_zoom_in_grows_scale_over_time():
    clip = ColorClip(size=(CANVAS_WIDTH, CANVAS_HEIGHT), color=(10, 20, 30), duration=2.0)
    composed = _apply_shot_effect(clip, "zoom_in", intensity=0.2)

    assert composed.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    assert composed.duration == 2.0


def test_apply_shot_effect_static_is_passthrough_sized_to_canvas():
    clip = ColorClip(size=(CANVAS_WIDTH, CANVAS_HEIGHT), color=(10, 20, 30), duration=1.5)
    composed = _apply_shot_effect(clip, "static")

    assert composed.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
    assert composed.duration == 1.5


def test_apply_shot_effect_pan_never_reveals_edge(tmp_path: Path):
    clip = ColorClip(size=(CANVAS_WIDTH, CANVAS_HEIGHT), color=(200, 0, 0), duration=1.0)
    composed = _apply_shot_effect(clip, "pan_left", intensity=0.2)

    for t in (0.0, 0.3, 0.6, 0.99):
        frame = composed.get_frame(t)
        # The solid-red source clip should fully cover the canvas at every
        # sampled time - no black (unfilled) edge pixels revealed by the pan.
        assert (frame[:, 0] != 0).any()
        assert (frame[:, -1] != 0).any()


def test_split_sentence_into_subshots_short_sentence_stays_one_shot():
    assert _split_sentence_into_subshots(1.5, min_shot=1.0, max_shot=2.5) == [1.5]


def test_split_sentence_into_subshots_long_sentence_splits_into_bounded_shots():
    shots = _split_sentence_into_subshots(6.0, min_shot=1.0, max_shot=2.5)
    assert len(shots) > 1
    assert sum(shots) == pytest.approx(6.0)
    for shot in shots:
        assert shot <= 2.5 + 1e-6


def test_split_sentence_into_subshots_avoids_too_short_final_shot():
    # 2.6s at max_shot=2.5 would naively want 2 shots of 1.3s each, which is
    # fine; but a duration like 2.05 at max_shot=1.0/min_shot=1.0 would want 3
    # shots of ~0.68s (< min_shot) - should collapse to fewer, longer shots.
    shots = _split_sentence_into_subshots(2.05, min_shot=1.0, max_shot=1.0)
    assert all(shot >= 1.0 - 1e-6 for shot in shots)


def test_pick_subclip_start_varies_across_reuse_indices():
    offsets = {_pick_subclip_start(10.0, 2.0, i) for i in range(1, 5)}
    assert len(offsets) > 1
    for offset in offsets:
        assert 0.0 <= offset <= 8.0


def test_pick_subclip_start_returns_zero_for_first_use():
    assert _pick_subclip_start(10.0, 2.0, reuse_index=0) == 0.0


def test_combine_videos_fills_full_canvas_with_no_letterboxing(tmp_path: Path):
    clip_a = tmp_path / "a.mp4"
    clip_b = tmp_path / "b.mp4"
    _make_clip(clip_a, width=640, height=360, duration=2.0)
    _make_clip(clip_b, width=640, height=360, duration=2.0)

    script = "This is one. This is two."
    words = [
        {"text": "This", "start": 0.0, "end": 0.3},
        {"text": "is", "start": 0.3, "end": 0.5},
        {"text": "one.", "start": 0.5, "end": 1.0},
        {"text": "This", "start": 1.0, "end": 1.3},
        {"text": "is", "start": 1.3, "end": 1.5},
        {"text": "two.", "start": 1.5, "end": 2.0},
    ]

    combined_path = combine_videos([[clip_a], [clip_b]], script, words, audio_duration=2.0)

    combined = VideoFileClip(str(combined_path))
    try:
        assert combined.size == [CANVAS_WIDTH, CANVAS_HEIGHT]
        assert combined.duration > 0
    finally:
        combined.close()


def test_combine_videos_loops_short_source_clip_without_crashing(tmp_path: Path):
    """Regression test: the old `int(max_duration / len(video_paths))` clip-
    looping math could evaluate to 0 (crashing concatenate_videoclips([])) once
    a single sentence's shot duration exceeded a short source clip's own
    duration. The new math.ceil-based loop must never do that."""
    short_clip = tmp_path / "short.mp4"
    _make_clip(short_clip, width=640, height=360, duration=0.4)  # shorter than any sub-shot

    script_words = [
        "A", "single", "long", "sentence", "that", "takes", "a", "while",
        "to", "say", "out", "loud", "here.",
    ]
    script = " ".join(script_words)
    words = [
        {"text": w, "start": i * 0.4, "end": (i + 1) * 0.4}
        for i, w in enumerate(script_words)
    ]
    audio_duration = words[-1]["end"]

    combined_path = combine_videos([[short_clip]], script, words, audio_duration)

    combined = VideoFileClip(str(combined_path))
    try:
        assert combined.duration > 0
    finally:
        combined.close()


def test_combine_videos_falls_back_to_placeholder_when_scene_is_empty(tmp_path: Path):
    script = "Only one sentence here."
    words = [
        {"text": "Only", "start": 0.0, "end": 0.3},
        {"text": "one", "start": 0.3, "end": 0.6},
        {"text": "sentence", "start": 0.6, "end": 1.0},
        {"text": "here.", "start": 1.0, "end": 1.5},
    ]

    combined_path = combine_videos([[]], script, words, audio_duration=1.5)

    combined = VideoFileClip(str(combined_path))
    try:
        assert combined.duration > 0
    finally:
        combined.close()
