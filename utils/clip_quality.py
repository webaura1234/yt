"""Scoring and rejection for candidate footage.

The previous pipeline took the first Pexels result that decoded. This module
exists so that never happens again: every candidate is measured, weak ones are
rejected outright, and the best of what survives wins.

Six of the seven signals are measured from the file itself with OpenCV rather
than taken from provider metadata, because metadata says what a clip is tagged
as and pixels say what it actually is. A clip tagged "ocean waves" that is
really a static hotel-brochure still scores badly on motion here, and no amount
of good tagging rescues it.

Semantic relevance is the exception: it cannot be read off the pixels, so it
comes from the query that found the clip plus the brief's own concept terms,
and is confirmed later by the editor review pass (utils/editor_review.py).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Footage that turns up for almost any query and means almost nothing. These are
# rejected unless the scene's brief explicitly says the narration is about them
# (SceneBrief.allow_generic) - a video about laptops is allowed a laptop.
GENERIC_BROLL_PATTERNS: Dict[str, Sequence[str]] = {
    "people walking": ("people walking", "crowd walking", "pedestrian", "commuters", "walking street"),
    "laptop": ("laptop", "typing keyboard", "coworking", "startup office", "business meeting"),
    "office": ("office", "boardroom", "conference room", "desk workspace"),
    "city traffic": ("city traffic", "highway traffic", "cars driving", "busy intersection"),
    "abstract background": (
        "abstract",
        "bokeh",
        "particle",
        "gradient background",
        "motion background",
        "digital background",
    ),
}

# Hints that a clip is rendered/animated rather than filmed. Only used to lower
# the realism score, never to reject on its own: a legitimately scientific
# animation may be the right shot for an explanatory line.
_SYNTHETIC_HINTS = ("3d render", "animation", "animated", "cgi", "render", "motion graphics")

# Below this a clip is not worth rendering: it is either irrelevant, a still, or
# visually broken. Tuned so that a clip failing any single dimension badly is
# rejected rather than averaged back into acceptability.
DEFAULT_MIN_SCORE = 0.45

_WEIGHTS = {
    "relevance": 0.34,
    "quality": 0.12,
    "realism": 0.10,
    "orientation": 0.12,
    "motion": 0.16,
    "composition": 0.11,
    "freshness": 0.05,
}


@dataclass
class ClipScore:
    """Per-dimension scores in 0..1, plus the weighted total."""

    relevance: float = 0.0
    quality: float = 0.0
    realism: float = 0.0
    orientation: float = 0.0
    motion: float = 0.0
    composition: float = 0.0
    freshness: float = 0.0
    rejected: bool = False
    reasons: List[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        if self.rejected:
            return 0.0
        return round(
            sum(getattr(self, dimension) * weight for dimension, weight in _WEIGHTS.items()), 3
        )

    def explain(self) -> str:
        """Short human-readable justification, for the storyboard table."""
        if self.rejected:
            return "rejected: " + "; ".join(self.reasons)
        ranked = sorted(
            ((getattr(self, d), d) for d in _WEIGHTS),
            reverse=True,
        )
        best = ", ".join(f"{name} {value:.2f}" for value, name in ranked[:3])
        return f"strongest: {best}"


@dataclass
class Candidate:
    """One downloaded clip, with where it came from."""

    path: Path
    query: str
    provider: str = "pexels"
    provider_id: str = ""
    width: int = 0
    height: int = 0
    duration: float = 0.0
    tags: str = ""


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2]


def matched_generic_category(text: str, allow: Sequence[str] = ()) -> Optional[str]:
    """Return the generic-B-roll category `text` falls into, if any.

    `allow` lists categories the narration is genuinely about, which are
    therefore permitted for this scene.
    """
    lowered = (text or "").lower()
    allowed = {a.lower() for a in allow}

    for category, patterns in GENERIC_BROLL_PATTERNS.items():
        if category in allowed:
            continue
        if any(pattern in lowered for pattern in patterns):
            return category
    return None


def semantic_relevance(candidate: Candidate, concept_terms: Sequence[str]) -> float:
    """Overlap between the concepts the scene needs and the text that found this
    clip.

    Deliberately conservative: with no concept terms (non-Latin narration and a
    failed brief) it returns a neutral 0.5 rather than a confident 1.0, so a
    clip is never promoted on evidence that doesn't exist. The editor review is
    what actually confirms meaning.
    """
    wanted = {t for term in concept_terms for t in _tokens(term)}
    if not wanted:
        return 0.5

    have = set(_tokens(f"{candidate.query} {candidate.tags}"))
    if not have:
        return 0.0

    return round(len(wanted & have) / len(wanted), 3)


def measure_clip(path: Path, samples: int = 12) -> Dict[str, float]:
    """Measure motion, composition and exposure from the file itself.

    Samples evenly across the clip rather than reading every frame: enough to
    tell a static shot from a moving one and an empty frame from a composed one,
    at a cost that scales with candidate count without dominating a run.
    """
    result = {"motion": 0.0, "composition": 0.0, "brightness": 0.0, "frames": 0.0}

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return result

    try:
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            return result

        indices = np.linspace(0, max(total - 1, 0), num=min(samples, max(total, 1)), dtype=int)
        previous = None
        diffs: List[float] = []
        edge_scores: List[float] = []
        brightnesses: List[float] = []

        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue

            small = cv2.resize(frame, (160, 90))
            grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            brightnesses.append(float(grey.mean()) / 255.0)

            # Edge density stands in for "is there anything composed in this
            # frame" - a gradient or bokeh plate has almost no edges, a real
            # scene with a subject has plenty.
            edges = cv2.Canny(grey, 60, 160)
            edge_scores.append(float((edges > 0).mean()))

            if previous is not None:
                diffs.append(float(np.abs(grey.astype(np.int16) - previous.astype(np.int16)).mean()))
            previous = grey

        result["frames"] = float(len(brightnesses))
        if diffs:
            # ~6 grey levels of mean inter-frame change is comfortably "moving".
            result["motion"] = float(np.clip(np.mean(diffs) / 6.0, 0.0, 1.0))
        if edge_scores:
            result["composition"] = float(np.clip(np.mean(edge_scores) / 0.12, 0.0, 1.0))
        if brightnesses:
            result["brightness"] = float(np.mean(brightnesses))
    finally:
        capture.release()

    return result


def orientation_score(width: int, height: int) -> float:
    """How well a source frames into 9:16 without throwing most of it away.

    Portrait scores best, square is fine, 16:9 is workable, and anything
    ultra-wide is poor because a 9:16 crop of it keeps a sliver of the image -
    which is exactly how subjects end up cut off.
    """
    if width <= 0 or height <= 0:
        return 0.0

    aspect = width / height
    if aspect <= 0.75:  # portrait, 3:4 or narrower
        return 1.0
    if aspect <= 1.05:  # square-ish
        return 0.85
    if aspect <= 1.85:  # up to 16:9
        return 0.6
    if aspect <= 2.5:
        return 0.3
    return 0.1


def quality_score(width: int, height: int, duration: float) -> float:
    """Resolution and usable length, capped so 4K isn't preferred for its own sake."""
    if width <= 0 or height <= 0:
        return 0.0

    shortest = min(width, height)
    resolution = float(np.clip(shortest / 1080.0, 0.0, 1.0))
    # Under ~2s there isn't enough to cut from; beyond ~6s adds nothing.
    length = float(np.clip((duration - 1.0) / 5.0, 0.0, 1.0)) if duration else 0.3
    return round(0.7 * resolution + 0.3 * length, 3)


def realism_score(candidate: Candidate, measured: Dict[str, float]) -> float:
    """Preference for filmed material over rendered or synthetic plates."""
    text = f"{candidate.query} {candidate.tags}".lower()
    score = 1.0

    if any(hint in text for hint in _SYNTHETIC_HINTS):
        score -= 0.45

    # A frame with almost no edges is a gradient or a blur plate, not a place.
    if measured.get("composition", 0.0) < 0.15:
        score -= 0.3

    return round(float(np.clip(score, 0.0, 1.0)), 3)


def freshness_score(candidate: Candidate, newest_id: Optional[int] = None) -> float:
    """Rough recency proxy.

    Pexels' API does not return an upload date, but its IDs increase over time,
    so a candidate's ID relative to the newest one in the same result set is the
    only recency signal available. It is weighted lowest of the seven for
    exactly that reason - it is a proxy, not a fact.
    """
    try:
        candidate_id = int(candidate.provider_id)
    except (TypeError, ValueError):
        return 0.5

    if not newest_id or newest_id <= 0:
        return 0.5

    return round(float(np.clip(candidate_id / newest_id, 0.0, 1.0)), 3)


def score_candidate(
    candidate: Candidate,
    concept_terms: Sequence[str],
    allow_generic: Sequence[str] = (),
    newest_id: Optional[int] = None,
    min_score: float = DEFAULT_MIN_SCORE,
) -> ClipScore:
    """Score one candidate and decide whether it is usable at all."""
    score = ClipScore()

    generic = matched_generic_category(f"{candidate.query} {candidate.tags}", allow_generic)
    if generic:
        score.rejected = True
        score.reasons.append(f"generic b-roll ({generic}) and the narration isn't about it")
        return score

    measured = measure_clip(candidate.path)
    if measured["frames"] < 2:
        score.rejected = True
        score.reasons.append("unreadable or too few frames")
        return score

    score.relevance = semantic_relevance(candidate, concept_terms)
    score.quality = quality_score(candidate.width, candidate.height, candidate.duration)
    score.orientation = orientation_score(candidate.width, candidate.height)
    score.motion = measured["motion"]
    score.composition = measured["composition"]
    score.realism = realism_score(candidate, measured)
    score.freshness = freshness_score(candidate, newest_id)

    # Hard rejections. These are failures no weighted average should be able to
    # rescue, because each one produces footage a viewer would notice.
    if score.motion < 0.06:
        score.rejected = True
        score.reasons.append("effectively a still frame")
    if measured["brightness"] < 0.06:
        score.rejected = True
        score.reasons.append("almost entirely black")
    if measured["brightness"] > 0.97:
        score.rejected = True
        score.reasons.append("blown out to white")
    if score.orientation < 0.2:
        score.rejected = True
        score.reasons.append("too wide to crop to 9:16 without losing the subject")

    if not score.rejected and score.total < min_score:
        score.rejected = True
        score.reasons.append(f"total {score.total} below minimum {min_score}")

    return score


def rank_candidates(
    candidates: Sequence[Candidate],
    concept_terms: Sequence[str],
    allow_generic: Sequence[str] = (),
    min_score: float = DEFAULT_MIN_SCORE,
) -> List[tuple]:
    """Score every candidate and return the survivors, best first.

    Returns [(candidate, score)]. An empty result means nothing in the pool was
    good enough, which callers must treat as "search again", never as "use the
    least bad one".
    """
    if not candidates:
        return []

    ids = []
    for candidate in candidates:
        try:
            ids.append(int(candidate.provider_id))
        except (TypeError, ValueError):
            continue
    newest_id = max(ids) if ids else None

    scored = []
    for candidate in candidates:
        score = score_candidate(
            candidate, concept_terms, allow_generic, newest_id, min_score
        )
        if score.rejected:
            logger.debug(f"Rejected {candidate.path.name}: {'; '.join(score.reasons)}")
            continue
        scored.append((candidate, score))

    scored.sort(key=lambda pair: pair[1].total, reverse=True)
    return scored


def perceptual_signature(path: Path) -> Optional[np.ndarray]:
    """Small greyscale thumbnail of the clip's middle frame.

    Used to tell whether two chosen clips look alike. Provider IDs only catch
    the identical file; stock libraries are full of near-duplicate shots from
    the same shoot, and cutting between two of those looks like a mistake.
    """
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return None
    try:
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(total // 2, 0))
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        grey = cv2.cvtColor(cv2.resize(frame, (32, 32)), cv2.COLOR_BGR2GRAY)
        return grey.astype(np.float32) / 255.0
    finally:
        capture.release()


def looks_like(signature_a: Optional[np.ndarray], signature_b: Optional[np.ndarray], threshold: float = 0.9) -> bool:
    """True when two clips are visually near-identical."""
    if signature_a is None or signature_b is None:
        return False

    a = signature_a.flatten() - signature_a.mean()
    b = signature_b.flatten() - signature_b.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0:
        return False

    return float(np.dot(a, b) / denominator) >= threshold
