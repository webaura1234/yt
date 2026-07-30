from pathlib import Path

from fastapi import APIRouter, HTTPException

import config
from api.schemas import DedupeResponse, MediaItem, MediaListResponse
from utils.downloads import dedupe_folder, delete_media_file, read_attribution

router = APIRouter(tags=["media"])


def _category_config() -> dict[str, tuple[Path, set[str], str]]:
    # Read config.* at call time (not import time) so the paths reflect whatever
    # the current config actually is - matters for tests that monkeypatch them.
    return {
        "music": (config.BACKGROUND_SONGS_PATH, {".mp3", ".wav"}, "/media/music"),
        "secondary_video": (
            config.SECONDARY_CONTENT_PATH,
            {".mp4"},
            "/media/secondary-video",
        ),
    }


def _list_category(category: str) -> list[MediaItem]:
    folder, extensions, url_prefix = _category_config()[category]
    if not folder.exists():
        return []

    items = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue

        attribution = read_attribution(path) or {}
        items.append(
            MediaItem(
                category=category,
                filename=path.name,
                size_bytes=path.stat().st_size,
                url=f"{url_prefix}/{path.name}",
                license=attribution.get("license") or None,
                credit=attribution.get("credit") or None,
                source_url=attribution.get("url") or None,
                attribution_required=bool(attribution.get("attribution_required")),
            )
        )
    return items


@router.get("/media", response_model=MediaListResponse)
def list_media() -> MediaListResponse:
    return MediaListResponse(
        music=_list_category("music"),
        secondary_video=_list_category("secondary_video"),
    )


@router.post("/media/dedupe", response_model=DedupeResponse)
def dedupe_media() -> DedupeResponse:
    categories = _category_config()
    music_folder, music_extensions, _ = categories["music"]
    video_folder, video_extensions, _ = categories["secondary_video"]

    return DedupeResponse(
        music_removed=(
            dedupe_folder(music_folder, music_extensions) if music_folder.exists() else 0
        ),
        secondary_video_removed=(
            dedupe_folder(video_folder, video_extensions) if video_folder.exists() else 0
        ),
    )


@router.delete("/media/{category}/{filename}", status_code=204)
def delete_media(category: str, filename: str) -> None:
    categories = _category_config()
    if category not in categories:
        raise HTTPException(status_code=404, detail="Unknown media category")

    folder, extensions, _ = categories[category]
    if not folder.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # filename comes straight from the URL - resolve and confirm it's still inside
    # the category folder before deleting anything (defends against ".." traversal).
    path = (folder / filename).resolve()
    if folder.resolve() not in path.parents:
        raise HTTPException(status_code=404, detail="File not found")

    if path.suffix.lower() not in extensions or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    delete_media_file(path)
