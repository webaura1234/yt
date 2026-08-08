"""Framing a source clip into the 9:16 canvas without amputating the subject.

The old behaviour was an unconditional cover-crop. Cover-cropping 16:9 into 9:16
keeps 31.6% of the width and throws away the rest, so any subject that isn't
dead centre gets sliced - which is exactly the "heavily zoomed, important things
cut off" failure. Centring the crop on a detected face helped only when there
was a face, and did nothing about how much was being discarded.

This module decides *how* to frame before it frames. It locates the subject,
works out whether a 9:16 crop can contain it, and if it cannot, refuses to crop:
the whole frame is fitted into the canvas over a blurred fill of itself, which
keeps every pixel of the subject at the cost of some background. Losing part of
the background is a cosmetic compromise. Losing half the subject is a broken
shot.

Zoom is capped hard at MAX_ZOOM. Nothing here is allowed to push in further just
to fill the canvas.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Hard ceiling on scaling a source up. Beyond this, footage visibly softens and
# the shot reads as a desperate crop rather than a choice.
MAX_ZOOM = 1.1

# A crop must retain at least this much of the subject's area to be allowed.
# Below it, we fit-with-blur instead.
MIN_SUBJECT_RETENTION = 0.92

_FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


class FramingMode(str, Enum):
    CROP = "crop"
    FIT_BLUR = "fit-blur"


@dataclass
class FramingPlan:
    """How one clip should be placed into the canvas."""

    mode: FramingMode
    # Crop box in source pixels; only meaningful for FramingMode.CROP.
    crop_width: float = 0.0
    crop_height: float = 0.0
    crop_x_center: float = 0.0
    crop_y_center: float = 0.0
    # Scale applied to the source. Never exceeds MAX_ZOOM.
    zoom: float = 1.0
    subject_retained: float = 1.0
    reason: str = ""

    def describe(self) -> str:
        return f"{self.mode.value} (zoom {self.zoom:.2f}, subject kept {self.subject_retained:.0%})"


def _face_boxes(frame: np.ndarray) -> list:
    """Face rectangles in a BGR frame, largest first."""
    try:
        cascade = cv2.CascadeClassifier(_FACE_CASCADE_PATH)
        if cascade.empty():
            return []
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(grey, scaleFactor=1.15, minNeighbors=5, minSize=(28, 28))
        return sorted(
            ([int(x), int(y), int(w), int(h)] for x, y, w, h in faces),
            key=lambda box: box[2] * box[3],
            reverse=True,
        )
    except Exception as e:
        logger.debug(f"Face detection failed: {e}")
        return []


def _salient_box(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Bounding box of the visually busiest region, as (x, y, w, h).

    A deliberate, dependency-free stand-in for a saliency model: detail density
    tracks where the subject is well enough to answer the only question being
    asked here - roughly which part of the frame must survive the crop. Uses
    edge energy, blurred into regions, thresholded generously.
    """
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(grey, 60, 160).astype(np.float32)
    energy = cv2.GaussianBlur(edges, (0, 0), sigmaX=max(frame.shape[1] / 40.0, 1.0))

    peak = float(energy.max())
    if peak <= 0:
        return None

    mask = (energy > peak * 0.35).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    xs0, ys0, xs1, ys1 = [], [], [], []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h < (frame.shape[0] * frame.shape[1]) * 0.01:
            continue
        xs0.append(x)
        ys0.append(y)
        xs1.append(x + w)
        ys1.append(y + h)

    if not xs0:
        return None

    x0, y0, x1, y1 = min(xs0), min(ys0), max(xs1), max(ys1)
    return x0, y0, x1 - x0, y1 - y0


def detect_subject_box(clip, samples: int = 5) -> Optional[Tuple[float, float, float, float]]:
    """Subject bounding box in source pixels as (x, y, w, h), or None.

    Sampled across the clip and unioned, so a subject that moves is contained by
    the box for the whole shot rather than only at the instant we looked. Faces
    win when present; otherwise the salient region is used.
    """
    if not clip.duration or clip.duration <= 0:
        return None

    times = np.linspace(0, max(clip.duration - 0.05, 0), num=samples)
    boxes = []

    for t in times:
        try:
            frame = clip.get_frame(float(t))
        except Exception:
            continue
        bgr = cv2.cvtColor(np.asarray(frame, dtype=np.uint8), cv2.COLOR_RGB2BGR)

        faces = _face_boxes(bgr)
        if faces:
            boxes.extend(faces)
            continue

        salient = _salient_box(bgr)
        if salient:
            boxes.append(list(salient))

    if not boxes:
        return None

    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)

    # Faces need headroom and shoulders, so pad the union slightly.
    pad_x = (x1 - x0) * 0.12
    pad_y = (y1 - y0) * 0.18
    x0 = max(x0 - pad_x, 0)
    y0 = max(y0 - pad_y, 0)
    x1 = min(x1 + pad_x, clip.w)
    y1 = min(y1 + pad_y, clip.h)

    return float(x0), float(y0), float(x1 - x0), float(y1 - y0)


def plan_framing(
    source_w: float,
    source_h: float,
    target_w: float,
    target_h: float,
    subject_box: Optional[Tuple[float, float, float, float]] = None,
    min_retention: float = MIN_SUBJECT_RETENTION,
) -> FramingPlan:
    """Decide between cropping and fitting. Pure math - no I/O, no moviepy.

    With no detected subject the crop is centred and allowed, because there is
    nothing identifiable to protect. With a subject, the crop is centred on it
    and then checked: if the box still can't contain the subject, we fit instead.
    """
    if source_w <= 0 or source_h <= 0:
        raise ValueError("source dimensions must be positive")

    target_ratio = target_w / target_h
    source_ratio = source_w / source_h

    if source_ratio > target_ratio:
        crop_h = source_h
        crop_w = source_h * target_ratio
    else:
        crop_w = source_w
        crop_h = source_w / target_ratio

    zoom = min(max(target_w / crop_w, target_h / crop_h), MAX_ZOOM)

    if subject_box is None:
        return FramingPlan(
            mode=FramingMode.CROP,
            crop_width=crop_w,
            crop_height=crop_h,
            crop_x_center=source_w / 2.0,
            crop_y_center=source_h / 2.0,
            zoom=zoom,
            subject_retained=1.0,
            reason="no distinct subject detected; centred crop",
        )

    sx, sy, sw, sh = subject_box
    subject_area = max(sw * sh, 1e-6)

    # Centre the crop on the subject, clamped inside the source.
    x_center = min(max(sx + sw / 2.0, crop_w / 2.0), source_w - crop_w / 2.0)
    y_center = min(max(sy + sh / 2.0, crop_h / 2.0), source_h - crop_h / 2.0)

    left = x_center - crop_w / 2.0
    top = y_center - crop_h / 2.0
    overlap_w = max(0.0, min(sx + sw, left + crop_w) - max(sx, left))
    overlap_h = max(0.0, min(sy + sh, top + crop_h) - max(sy, top))
    retained = (overlap_w * overlap_h) / subject_area

    if retained >= min_retention:
        return FramingPlan(
            mode=FramingMode.CROP,
            crop_width=crop_w,
            crop_height=crop_h,
            crop_x_center=x_center,
            crop_y_center=y_center,
            zoom=zoom,
            subject_retained=round(retained, 3),
            reason="subject fits inside a 9:16 crop",
        )

    return FramingPlan(
        mode=FramingMode.FIT_BLUR,
        zoom=1.0,
        subject_retained=1.0,
        reason=(
            f"a 9:16 crop would cut {1 - retained:.0%} of the subject; "
            "fitting the whole frame over a blurred fill instead"
        ),
    )


def fit_with_blur(clip, target_w: int, target_h: int, blur_strength: int = 45):
    """Whole frame fitted inside the canvas, over a blurred, zoomed copy of itself.

    Used when cropping would cut the subject. Keeps 100% of the source visible;
    the background is the shot's own colours so it reads as intentional rather
    than as letterboxing.
    """
    from moviepy.editor import CompositeVideoClip

    scale = min(target_w / clip.w, target_h / clip.h)
    foreground = clip.resize(scale)

    cover_scale = max(target_w / clip.w, target_h / clip.h)
    background = clip.resize(cover_scale)

    def blur_frame(frame):
        # Downsample then upsample: a cheap, strong blur that costs far less
        # than a large-kernel Gaussian at 1080x1920, per frame.
        small = cv2.resize(
            frame,
            (max(frame.shape[1] // blur_strength, 2), max(frame.shape[0] // blur_strength, 2)),
            interpolation=cv2.INTER_AREA,
        )
        blurred = cv2.resize(small, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        return (blurred * 0.75).astype("uint8")

    background = background.fl_image(blur_frame)

    # Centre-crop the oversized background down to the canvas.
    bx = max((background.w - target_w) / 2.0, 0)
    by = max((background.h - target_h) / 2.0, 0)
    background = background.crop(x1=bx, y1=by, x2=bx + target_w, y2=by + target_h)

    composite = CompositeVideoClip(
        [background, foreground.set_position("center")], size=(target_w, target_h)
    )
    return composite.set_duration(clip.duration)


def apply_framing(clip, plan: FramingPlan, target_w: int, target_h: int):
    """Realise a FramingPlan against a clip."""
    from moviepy.video.fx.all import crop as crop_fx

    if plan.mode is FramingMode.FIT_BLUR:
        return fit_with_blur(clip, target_w, target_h)

    cropped = crop_fx(
        clip,
        width=int(plan.crop_width),
        height=int(plan.crop_height),
        x_center=plan.crop_x_center,
        y_center=plan.crop_y_center,
    )
    return cropped.resize((target_w, target_h))


def frame_clip(clip, target_w: int, target_h: int, detect: bool = True):
    """Detect the subject, plan the framing, apply it. Returns (clip, plan)."""
    subject_box = None
    if detect:
        try:
            subject_box = detect_subject_box(clip)
        except Exception as e:
            logger.warning(f"Subject detection failed, framing without it: {e}")

    plan = plan_framing(clip.w, clip.h, target_w, target_h, subject_box)
    logger.info(f"Framing: {plan.describe()} - {plan.reason}")
    return apply_framing(clip, plan, target_w, target_h), plan
