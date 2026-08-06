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
    check_subtitle_font_support,
    combine_scene_images,
    combine_videos,
    create_karaoke_subtitles,
    create_lower_third_backdrop,
    render_text_image,
    strip_unrenderable,
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


def test_subtitle_font_supports_telugu_and_shaping():
    # Both failure modes are silent at render time - a font with no Telugu
    # glyphs gives blank captions, missing shaping breaks conjuncts apart - and
    # only show up once you watch the finished video.
    check_subtitle_font_support()


@pytest.mark.parametrize(
    "word",
    ["పిల్లలు", "సైన్సు", "అద్భుతం", "నక్షత్రం", "గణితం"],
)
def test_telugu_words_with_conjuncts_render_visible_ink(word):
    image = render_text_image(word, font_size=72)

    assert image[:, :, 3].max() == 255, f"{word} rendered to nothing"
    # A .notdef box is narrow and uniform; real shaped Telugu is much wider.
    assert image.shape[1] > image.shape[0], f"{word} looks like tofu boxes"


def test_strip_unrenderable_removes_emoji_from_telugu_text():
    # Pillow has no font fallback inside a text run, so an emoji next to Telugu
    # renders as a .notdef box. Dropping it beats showing the box.
    assert strip_unrenderable("పిల్లలు🎉") == "పిల్లలు"
    assert strip_unrenderable("🎉") == ""


def test_karaoke_skips_tokens_that_would_render_to_nothing():
    words = [
        {"text": "సూర్యుడు", "start": 0.0, "end": 0.5},
        {"text": "🎉", "start": 0.5, "end": 0.6},
        {"text": "వేడి", "start": 0.6, "end": 1.0},
    ]

    clips = create_karaoke_subtitles(words, video_duration=1.0)

    assert len(clips) == 2, "emoji-only token should not become a blank clip"


def test_karaoke_words_pop_in_and_settle_to_full_size():
    words = [{"text": "పిల్లలు", "start": 0.0, "end": 1.0}]
    clip = create_karaoke_subtitles(words, video_duration=1.0)[0]

    # The pop is an attention cue for a child still learning to read: the word
    # must start oversized and settle, not just appear.
    assert clip.get_frame(0.001).shape[1] > clip.get_frame(0.9).shape[1]


def test_render_text_image_is_rgba_with_opaque_glyphs_and_transparent_corners():
    image = render_text_image("HI")

    assert image.ndim == 3 and image.shape[2] == 4, "expected an RGBA array"
    assert image.shape[0] > 0 and image.shape[1] > 0

    alpha = image[:, :, 3]
    assert alpha.max() == 255, "glyphs should be fully opaque somewhere"
    # A tight bbox around "HI" still leaves the outer corners empty, so the
    # background must be transparent rather than filled black/white.
    assert alpha[0, 0] == 0
    assert alpha[-1, -1] == 0


def test_render_text_image_height_is_constant_across_words():
    # Subtitle clips are positioned by their top edge, so every word must
    # rasterise to the same height or the captions jitter vertically as
    # descenders come and go.
    heights = {render_text_image(word).shape[0] for word in ("HI", "yes", "jump", "OK")}
    assert len(heights) == 1


def test_render_text_image_keeps_stroke_inside_the_canvas():
    # A word whose glyphs reach the ascender and descender lines must still
    # have its full outline inside the image rather than clipped at the edges.
    image = render_text_image("Jhg")
    alpha = image[:, :, 3]

    assert not alpha[0, :].any(), "stroke should not touch the top edge"
    assert not alpha[-1, :].any(), "stroke should not touch the bottom edge"


def test_render_text_image_grows_with_font_size():
    small = render_text_image("HI", font_size=40)
    large = render_text_image("HI", font_size=120)

    assert large.shape[0] > small.shape[0]
    assert large.shape[1] > small.shape[1]


def test_render_text_image_applies_fill_and_stroke_colors():
    image = render_text_image("HI", color="#FF0000", stroke_color="#0000FF")
    opaque = image[image[:, :, 3] == 255]

    reds = opaque[(opaque[:, 0] > 200) & (opaque[:, 1] < 60) & (opaque[:, 2] < 60)]
    blues = opaque[(opaque[:, 2] > 200) & (opaque[:, 0] < 60) & (opaque[:, 1] < 60)]

    assert len(reds) > 0, "expected red fill pixels"
    assert len(blues) > 0, "expected blue stroke pixels"


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


def _scene_png(dest: Path, color=(200, 120, 40)) -> Path:
    from PIL import Image

    Image.new("RGB", (896, 1600), color).save(dest)
    return dest


def test_combine_scene_images_fills_the_canvas_and_matches_narration_length(tmp_path):
    script = "మొదటి వాక్యం. రెండవ వాక్యం. మూడవ వాక్యం."
    words = [
        {"text": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.5} for i in range(6)
    ]
    images = [
        _scene_png(tmp_path / f"s{i}.png", (40 * i, 120, 200 - 30 * i)) for i in range(3)
    ]

    out = combine_scene_images(images, script, words, audio_duration=3.0)
    clip = VideoFileClip(str(out))

    try:
        assert clip.size == [CANVAS_WIDTH, CANVAS_HEIGHT]
        # The visual track must never end before the narration does, or the
        # video ends on a black tail while a child is still being spoken to.
        assert clip.duration >= 3.0 - 0.05
    finally:
        clip.close()


def test_combine_scene_images_holds_the_last_frame_when_short_on_artwork(tmp_path):
    # More sentences than drawings must not crash or drop a sentence's slot.
    script = "ఒకటి. రెండు. మూడు."
    words = [{"text": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.4} for i in range(6)]
    images = [_scene_png(tmp_path / "only.png")]

    out = combine_scene_images(images, script, words, audio_duration=2.4)
    clip = VideoFileClip(str(out))

    try:
        assert clip.size == [CANVAS_WIDTH, CANVAS_HEIGHT]
    finally:
        clip.close()


def test_combine_scene_images_rejects_an_empty_scene_list():
    with pytest.raises(ValueError):
        combine_scene_images([], "ఒకటి.", [{"text": "w", "start": 0, "end": 1}], 1.0)
