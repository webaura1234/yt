"""Cartoon artwork for every sentence of the narration.

This replaces the stock-footage sourcing the pipeline used to do. Stock video
cannot show a recurring character spilling a bucket on their own head, and a
children's channel illustrated with unrelated clips of strangers reads as an
automation pipeline, not a studio. So each sentence gets its own drawing.

Cost shape: one image call per sentence, roughly 8-14 per video, which makes
this the most expensive stage of a run. Frames are therefore cached on disk by
prompt hash and reused forever - the same prompt is never paid for twice.

Failure is expected and handled. Image generation is the newest and least
reliable dependency in the pipeline, and a children's video that fails to render
at all is worse than one with plainer artwork, so a scene that cannot be drawn
falls back to a generated pattern card rather than aborting the video.
"""

import base64
import hashlib
import logging
import math
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
from PIL import Image

from config import CARTOON_CACHE_PATH, GEMINI_API_KEY, GEMINI_IMAGE_MODEL

logger = logging.getLogger(__name__)

# Portrait, matching the Shorts canvas. Generated a little smaller than the
# 1080x1920 canvas and upscaled during the Ken Burns move, which costs nothing
# visually because the frame is always being scaled anyway.
SCENE_WIDTH = 896
SCENE_HEIGHT = 1600

_TIMEOUT_SECONDS = 120

# Palettes for the fallback cards: bright, warm and childlike, so a degraded
# render still looks like it belongs to this channel rather than like an error.
_FALLBACK_PALETTES = (
    ((255, 214, 102), (255, 138, 101)),
    ((129, 212, 250), (149, 117, 205)),
    ((174, 213, 129), (77, 182, 172)),
    ((255, 171, 145), (240, 98, 146)),
    ((255, 245, 157), (255, 167, 38)),
)


def _cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]


def _cached_path(prompt: str) -> Path:
    return CARTOON_CACHE_PATH / f"{_cache_key(prompt)}.png"


def _request_image(prompt: str) -> Optional[bytes]:
    """Ask Gemini for one image. Returns raw PNG/JPEG bytes, or None on failure.

    Never raises: every caller has a usable fallback, and one unlucky scene
    should not take down a whole video.
    """
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY set; cannot generate cartoon artwork")
        return None

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_IMAGE_MODEL}:generateContent"
    )
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning(f"Cartoon image request failed: {e}")
        return None

    try:
        for part in data["candidates"][0]["content"]["parts"]:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    except Exception as e:
        logger.warning(f"Cartoon image response could not be parsed: {e}")
        return None

    logger.warning("Cartoon image response contained no image data")
    return None


def _fallback_card(prompt: str, width: int, height: int) -> Image.Image:
    """A bright gradient card with soft blobs, used when no image can be drawn.

    Deterministic in the prompt, so consecutive scenes get visibly different
    cards instead of the whole video collapsing to one flat colour - the
    fallback still has to hold a child's attention for a few seconds.
    """
    seed = int(_cache_key(prompt), 16)
    top, bottom = _FALLBACK_PALETTES[seed % len(_FALLBACK_PALETTES)]

    ramp = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    gradient = (
        np.array(top, dtype=np.float32)[None, None, :] * (1 - ramp[:, :, None])
        + np.array(bottom, dtype=np.float32)[None, None, :] * ramp[:, :, None]
    )
    canvas = np.repeat(gradient, width, axis=1)

    # A few translucent circles so the card has some shape to look at.
    yy, xx = np.mgrid[0:height, 0:width]
    for i in range(3):
        cx = (seed >> (8 * i + 1)) % width
        cy = (seed >> (8 * i + 5)) % height
        radius = min(width, height) * (0.18 + 0.06 * i)
        mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < radius**2
        canvas[mask] = canvas[mask] * 0.82 + 255 * 0.18

    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))


def _fit_to_canvas(image: Image.Image, width: int, height: int) -> Image.Image:
    """Cover-crop to exactly (width, height), preserving aspect ratio.

    The model is asked for portrait but does not always obey, and a letterboxed
    frame inside a Shorts canvas looks broken. Cropping keeps the frame full.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(1, math.ceil(image.width * scale)), max(1, math.ceil(image.height * scale))),
        Image.LANCZOS,
    )

    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def generate_scene_image(
    prompt: str, width: int = SCENE_WIDTH, height: int = SCENE_HEIGHT
) -> Path:
    """Return a path to the artwork for one sentence, drawing it if needed.

    Always returns a usable image path - a failed generation yields a fallback
    card rather than an exception.
    """
    cached = _cached_path(prompt)
    if cached.exists():
        logger.debug(f"Cartoon cache hit: {cached.name}")
        return cached

    raw = _request_image(prompt)

    if raw is not None:
        try:
            import io

            image = _fit_to_canvas(Image.open(io.BytesIO(raw)), width, height)
        except Exception as e:
            logger.warning(f"Generated cartoon could not be decoded, using fallback: {e}")
            image = _fallback_card(prompt, width, height)
    else:
        image = _fallback_card(prompt, width, height)

    cached.parent.mkdir(parents=True, exist_ok=True)
    image.save(cached, format="PNG")
    return cached


def generate_scene_images(
    prompts: List[str], width: int = SCENE_WIDTH, height: int = SCENE_HEIGHT
) -> List[Path]:
    """Artwork for every sentence, in narration order.

    `len(result) == len(prompts)` always holds, so the renderer can pair frames
    to sentences positionally without defending against gaps.
    """
    paths = [generate_scene_image(p, width, height) for p in prompts]

    drawn = sum(1 for p in paths if p.exists())
    logger.info(f"Prepared {drawn}/{len(prompts)} scene illustrations")
    return paths
