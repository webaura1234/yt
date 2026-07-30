import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from config import PEXELS_API_KEY, SCENE_CANDIDATES_PER_SCENE, TEMP_PATH
from utils.downloads import delete_media_file, download_file
from utils.video import (
    _SECONDARY_VIDEO_SEARCH_TERMS,
    _search_pexels_video_candidates,
    _validate_video_file,
)

logger = logging.getLogger(__name__)

_PEXELS_VIDEO_ID_RE = re.compile(r"video-files/(\d+)/")


@dataclass
class Scene:
    query: str
    clip_paths: List[Path] = field(default_factory=list)


def _extract_pexels_id(url: str) -> str:
    """Best-effort parse of the Pexels video ID from its CDN URL, used for
    cross-scene dedup; falls back to the full URL when the pattern doesn't
    match, so dedup still works (just less precisely) rather than crashing."""
    match = _PEXELS_VIDEO_ID_RE.search(url)
    return match.group(1) if match else url


def _broaden_query(query: str) -> str:
    """Cheap, non-LLM broadening: keeps only the trailing core noun(s), giving
    a too-specific query one more chance before falling back to borrowing/
    generic B-roll."""
    words = query.split()
    if len(words) <= 2:
        return query
    return " ".join(words[-2:])


def _download_and_validate_candidates(
    urls: List[str], used_pexels_ids: Set[str], limit: int
) -> List[Path]:
    """Downloads and validates up to `limit` distinct, not-yet-used candidates
    from `urls`, marking each successfully validated one as used immediately so
    later scenes can't also pick it."""
    kept = []
    for url in urls:
        if len(kept) >= limit:
            break

        pexels_id = _extract_pexels_id(url)
        if pexels_id in used_pexels_ids:
            continue

        dest = TEMP_PATH / f"{uuid.uuid4()}.mp4"
        if not download_file(url, dest):
            continue
        if not _validate_video_file(dest, min_duration=1.0, min_width=480, require_landscape=False):
            delete_media_file(dest)
            continue

        used_pexels_ids.add(pexels_id)
        kept.append(dest)

    return kept


def fetch_scene_candidates(
    search_terms: List[str], candidates_per_scene: int = SCENE_CANDIDATES_PER_SCENE
) -> List[Scene]:
    """One Pexels search per search_term/sentence (candidates_per_scene doesn't
    add extra API calls - it only controls how many of that single search's
    results we keep, for ranking/sub-shot variety/dedup fallback). Threads a
    run-scoped `used_pexels_ids` set through every scene so later sentences
    can't reuse footage an earlier sentence already claimed.

    Per-scene fallback chain when the exact query yields nothing usable:
    broadened query -> borrow from an adjacent scene's pool -> last-resort
    generic B-roll (logged at WARNING so it stays rare and visible)."""
    used_pexels_ids: Set[str] = set()
    scenes: List[Scene] = []

    for term in search_terms:
        clip_paths: List[Path] = []

        if PEXELS_API_KEY:
            urls = _search_pexels_video_candidates(term, per_page=8, orientation=None)
            clip_paths = _download_and_validate_candidates(urls, used_pexels_ids, candidates_per_scene)

            if not clip_paths:
                broadened = _broaden_query(term)
                if broadened != term:
                    urls = _search_pexels_video_candidates(broadened, per_page=8, orientation=None)
                    clip_paths = _download_and_validate_candidates(
                        urls, used_pexels_ids, candidates_per_scene
                    )

        scenes.append(Scene(query=term, clip_paths=clip_paths))

    for i, scene in enumerate(scenes):
        if scene.clip_paths:
            continue

        for neighbor_idx in (i - 1, i + 1):
            if 0 <= neighbor_idx < len(scenes) and scenes[neighbor_idx].clip_paths:
                scene.clip_paths = scenes[neighbor_idx].clip_paths[:1]
                logger.warning(
                    f"Scene '{scene.query}' had no usable footage; borrowing from "
                    f"adjacent scene '{scenes[neighbor_idx].query}'"
                )
                break

        if scene.clip_paths or not PEXELS_API_KEY:
            continue

        for fallback_term in _SECONDARY_VIDEO_SEARCH_TERMS:
            urls = _search_pexels_video_candidates(fallback_term, per_page=8, orientation=None)
            clip_paths = _download_and_validate_candidates(urls, used_pexels_ids, 1)
            if clip_paths:
                logger.warning(
                    f"Scene '{scene.query}' had no usable footage at all; "
                    f"falling back to generic B-roll '{fallback_term}'"
                )
                scene.clip_paths = clip_paths
                break

    return scenes
