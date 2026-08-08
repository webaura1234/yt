import numpy as np
import pytest
from moviepy.editor import VideoClip

from utils.framing import (
    MAX_ZOOM,
    FramingMode,
    apply_framing,
    detect_subject_box,
    frame_clip,
    plan_framing,
)

CANVAS = (1080, 1920)


def test_zoom_never_exceeds_the_cap_for_any_source_shape():
    # Pushing in further than this visibly softens footage and reads as a
    # desperate crop. It is a hard ceiling, not a preference.
    shapes = [(1920, 1080), (3840, 2160), (640, 360), (320, 180), (1080, 1920), (720, 720)]

    for width, height in shapes:
        plan = plan_framing(width, height, *CANVAS)
        assert plan.zoom <= MAX_ZOOM + 1e-9, f"{width}x{height} zoomed to {plan.zoom}"


def test_centred_small_subject_is_cropped_normally():
    plan = plan_framing(1920, 1080, *CANVAS, subject_box=(860, 440, 200, 200))

    assert plan.mode is FramingMode.CROP
    assert plan.subject_retained == 1.0


def test_subject_wider_than_the_crop_switches_to_fit_with_blur():
    # A 9:16 crop of 16:9 keeps ~608px of width. A 1300px-wide subject cannot
    # survive it, so cropping would amputate the thing the shot is about.
    plan = plan_framing(1920, 1080, *CANVAS, subject_box=(300, 300, 1300, 500))

    assert plan.mode is FramingMode.FIT_BLUR
    assert "cut" in plan.reason


def test_subject_against_the_edge_is_not_sliced():
    plan = plan_framing(1920, 1080, *CANVAS, subject_box=(40, 400, 700, 300))

    assert plan.mode is FramingMode.FIT_BLUR


def test_crop_is_recentred_onto_an_off_centre_subject():
    plan = plan_framing(1920, 1080, *CANVAS, subject_box=(1300, 400, 300, 300))

    assert plan.mode is FramingMode.CROP
    # Centred on the subject (x=1450), not on the frame (x=960).
    assert plan.crop_x_center > 1000
    assert plan.subject_retained >= 0.92


def test_crop_box_never_extends_past_the_source():
    plan = plan_framing(1920, 1080, *CANVAS, subject_box=(1850, 500, 60, 60))

    assert plan.mode is FramingMode.CROP
    assert plan.crop_x_center + plan.crop_width / 2 <= 1920 + 1e-6
    assert plan.crop_x_center - plan.crop_width / 2 >= -1e-6


def test_no_subject_falls_back_to_a_centred_crop():
    plan = plan_framing(1920, 1080, *CANVAS)

    assert plan.mode is FramingMode.CROP
    assert plan.crop_x_center == pytest.approx(960)
    assert plan.crop_y_center == pytest.approx(540)


def test_portrait_source_needs_almost_no_crop():
    plan = plan_framing(1080, 1920, *CANVAS)

    assert plan.mode is FramingMode.CROP
    assert plan.crop_width == pytest.approx(1080)


def test_zero_sized_source_is_rejected():
    with pytest.raises(ValueError):
        plan_framing(0, 1080, *CANVAS)


def _wide_subject_clip():
    """A 16:9 shot whose subject is a wide band with five distinct markers."""

    def make(t):
        frame = np.full((1080, 1920, 3), 30, dtype=np.uint8)
        frame[400:700, 300:1600] = (240, 200, 60)
        for x in range(360, 1600, 250):
            frame[470:630, x : x + 90] = (200, 40, 40)
        return frame

    return VideoClip(make, duration=1.0).set_fps(12)


def _count_markers(frame: np.ndarray) -> int:
    red = (frame[:, :, 0] > 150) & (frame[:, :, 1] < 90) & (frame[:, :, 2] < 90)
    columns = np.where(red.any(axis=0))[0]
    if len(columns) == 0:
        return 0
    return 1 + int((np.diff(columns) > 1).sum())


def test_fit_with_blur_keeps_the_whole_subject_that_a_crop_would_cut():
    clip = _wide_subject_clip()
    source_markers = _count_markers(clip.get_frame(0).astype(np.uint8))
    assert source_markers == 5

    cropped = apply_framing(clip, plan_framing(1920, 1080, *CANVAS), *CANVAS)
    fitted = apply_framing(
        clip,
        plan_framing(1920, 1080, *CANVAS, subject_box=(300, 400, 1300, 300)),
        *CANVAS,
    )

    cropped_markers = _count_markers(cropped.get_frame(0.5).astype(np.uint8))
    fitted_markers = _count_markers(fitted.get_frame(0.5).astype(np.uint8))

    assert cropped_markers < source_markers, "the centred crop should lose markers"
    assert fitted_markers == source_markers, "fit-with-blur must keep every marker"


def test_framing_always_produces_exactly_the_canvas_size():
    clip = _wide_subject_clip()

    for subject in (None, (300, 400, 1300, 300), (860, 440, 200, 200)):
        plan = plan_framing(1920, 1080, *CANVAS, subject_box=subject)
        framed = apply_framing(clip, plan, *CANVAS)
        assert framed.size == list(CANVAS) or tuple(framed.size) == CANVAS


def test_detect_subject_box_finds_a_bright_object():
    def make(t):
        frame = np.full((1080, 1920, 3), 15, dtype=np.uint8)
        frame[300:800, 1200:1700] = (250, 250, 250)
        return frame

    clip = VideoClip(make, duration=0.5).set_fps(10)
    box = detect_subject_box(clip, samples=2)

    assert box is not None
    x, y, w, h = box
    # The detected region should sit on the right-hand side where the object is.
    assert x + w / 2 > 960


def test_frame_clip_returns_a_plan_describing_what_it_did():
    clip = _wide_subject_clip()
    framed, plan = frame_clip(clip, *CANVAS)

    assert plan.mode in (FramingMode.CROP, FramingMode.FIT_BLUR)
    assert plan.zoom <= MAX_ZOOM + 1e-9
    assert plan.describe()
    assert tuple(framed.size) == CANVAS
