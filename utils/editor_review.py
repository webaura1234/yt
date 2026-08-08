"""The review an editor does before committing to a cut.

Scoring (utils/clip_quality.py) can measure whether a clip is sharp, moving,
well-framed and lexically related to the query. It cannot see the clip, so it
cannot answer the question that actually matters: does this footage *show what
this sentence says*. A clip found by the query "crescent moon night sky" scores
perfectly whether it contains the moon or a streetlight.

So the chosen frame is looked at. A real frame from the clip, framed exactly as
it will appear in the render, is sent to a vision model with the sentence it has
to illustrate, and four direct questions. A rejection sends the scene back to
search with fresh queries rather than being noted and ignored.

When no vision model is available this degrades to a conservative check that
approves on measured evidence alone and says so - it never fabricates a verdict
it did not obtain.
"""

import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import requests
from PIL import Image

from config import GEMINI_API_KEY, GEMINI_TEXT_MODEL

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 90

# Below this the reviewer's own confidence is too low to trust an approval.
_MIN_CONFIDENCE = 0.5


@dataclass
class Review:
    """The verdict on one selected clip."""

    approved: bool
    represents_sentence: bool = False
    subject_visible: bool = False
    important_content_cropped: bool = False
    confidence: float = 0.0
    reason: str = ""
    better_queries: Optional[List[str]] = None
    reviewed_by_vision: bool = False

    def __post_init__(self):
        if self.better_queries is None:
            self.better_queries = []

    def summary(self) -> str:
        verdict = "approved" if self.approved else "rejected"
        how = "vision" if self.reviewed_by_vision else "heuristic"
        return f"{verdict} ({how}): {self.reason}"


def frame_to_png_bytes(frame: np.ndarray, max_edge: int = 512) -> bytes:
    """Downscale a rendered frame for review.

    Sent small on purpose: the questions are about what the shot contains and
    whether anything is cut off, all answerable at this size, and a full
    1080x1920 frame per scene would dominate both cost and latency.
    """
    image = Image.fromarray(np.asarray(frame, dtype=np.uint8))
    image.thumbnail((max_edge, max_edge))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _call_vision(prompt: str, png_bytes: bytes) -> Optional[dict]:
    """Ask the vision model the review questions. None if unavailable."""
    if not GEMINI_API_KEY:
        return None

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_TEXT_MODEL}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(png_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
            json=payload,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Editor review vision call failed: {e}")
        return None


def _heuristic_review(brief, score) -> Review:
    """Fallback verdict from measured signals only.

    Deliberately does not claim to have judged meaning. It approves what the
    scoring stage already vouched for and flags that no one looked at it, so a
    run without a vision model is visibly less verified rather than silently so.
    """
    strong = score is not None and score.total >= 0.6
    return Review(
        approved=strong,
        represents_sentence=False,
        subject_visible=score is not None and score.composition >= 0.3,
        important_content_cropped=False,
        confidence=0.35,
        reason=(
            "no vision model available; approved on measured score alone"
            if strong
            else "no vision model available and the measured score was weak"
        ),
        reviewed_by_vision=False,
    )


def review_clip(brief, frame: np.ndarray, score=None, crop_mode: str = "crop") -> Review:
    """Judge whether one framed clip actually illustrates its sentence.

    `frame` must be the frame as it will appear in the finished video - already
    cropped or fitted - because "is anything important cut off" is a question
    about the final framing, not about the source file.
    """
    prompt = f"""
You are a strict video editor reviewing one shot before it goes into a cut.

The shot must illustrate this narration line:
"{brief.sentence}"

What the line is about:
- subject: {brief.subject or "(unknown)"}
- action: {brief.action or "(unspecified)"}
- location: {brief.location or "(unspecified)"}
- objects that should be visible: {", ".join(brief.objects) or "(none specified)"}

The attached image is a real frame from the shot, framed exactly as it will
appear in the finished vertical video (framing mode: {crop_mode}).

Answer these four questions about the IMAGE, honestly and strictly:
1. Does this image visually represent that narration line? A viewer watching
   with the sound off should understand roughly what the line is about.
2. Is the main subject clearly visible and identifiable?
3. Is anything important cut off at the edges of the frame?
4. If this shot is wrong, what should we search for instead?

Be strict. Generic footage that is merely "related to the topic" does NOT
represent the line. If the image is an unrelated stock shot, say so.

Respond with JSON only:
{{
  "represents_sentence": true/false,
  "subject_visible": true/false,
  "important_content_cropped": true/false,
  "confidence": 0.0-1.0,
  "reason": "one short sentence",
  "better_queries": ["2-6 word search", "..."]
}}
"""

    png = frame_to_png_bytes(frame)
    payload = _call_vision(prompt, png)

    if payload is None:
        return _heuristic_review(brief, score)

    represents = bool(payload.get("represents_sentence"))
    visible = bool(payload.get("subject_visible"))
    cropped = bool(payload.get("important_content_cropped"))
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    queries = payload.get("better_queries", [])
    if not isinstance(queries, list):
        queries = []
    queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]

    approved = represents and visible and not cropped and confidence >= _MIN_CONFIDENCE

    return Review(
        approved=approved,
        represents_sentence=represents,
        subject_visible=visible,
        important_content_cropped=cropped,
        confidence=round(confidence, 2),
        reason=str(payload.get("reason", ""))[:200] or "no reason given",
        better_queries=queries,
        reviewed_by_vision=True,
    )
