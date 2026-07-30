import logging
from pathlib import Path
from typing import List

from utils.scenes import fetch_scene_candidates

logger = logging.getLogger(__name__)


def get_stock_videos(search_terms: List[str]) -> List[List[Path]]:
    """Returns one candidate-clip pool per search term/sentence (see
    utils.scenes.fetch_scene_candidates). Raises only if every single scene
    ended up with zero usable candidates."""
    scenes = fetch_scene_candidates(search_terms)

    if all(not scene.clip_paths for scene in scenes):
        logger.error("No stock videos found")
        raise Exception("No stock videos found")

    return [scene.clip_paths for scene in scenes]
