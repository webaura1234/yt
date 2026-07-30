import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from api.jobs.store import JobStage, update_job
from utils.audio import DEFAULT_VOICE, generate_voiceover
from utils.llm import (
    get_description,
    get_most_engaging_titles,
    get_script,
    get_search_terms,
    get_titles,
)
from utils.metadata import save_metadata
from utils.stock_videos import get_stock_videos
from utils.video import generate_video
from utils.yt import auto_upload

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], Awaitable[None]]
ShouldCancel = Callable[[], bool]


class JobCancelled(Exception):
    pass


def _check_cancel(should_cancel: ShouldCancel) -> None:
    if should_cancel():
        raise JobCancelled()


async def run_script_stage(
    job_id: str, topic: str, progress: ProgressCallback, should_cancel: ShouldCancel
) -> None:
    """Stage 1: topic -> titles -> script -> description -> search terms, then pause.

    Reuses utils/llm.py exactly as main.py does today - no generation logic changes."""
    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.GENERATING_SCRIPT)
    await progress("generating_script", "Generating title ideas...")

    titles = await asyncio.to_thread(get_titles, topic)
    best_titles = await asyncio.to_thread(get_most_engaging_titles, titles, 1)
    title = best_titles[0] if best_titles else topic

    _check_cancel(should_cancel)
    await progress("generating_script", f'Writing script for: "{title}"')
    script = await asyncio.to_thread(get_script, title)

    _check_cancel(should_cancel)
    await progress("generating_script", "Writing description...")
    description = await asyncio.to_thread(get_description, title, script)

    _check_cancel(should_cancel)
    await progress("generating_script", "Extracting search terms for footage...")
    search_terms = await asyncio.to_thread(get_search_terms, title, script)

    update_job(
        job_id,
        stage=JobStage.SCRIPT_READY,
        title=title,
        script=script,
        description=description,
        search_terms=search_terms,
    )
    await progress("script_ready", "Script ready for review.")


async def run_render_stage(
    job_id: str,
    job: dict[str, Any],
    voice: Optional[str],
    progress: ProgressCallback,
    should_cancel: ShouldCancel,
) -> dict[str, Any]:
    """Stage 2: media + voiceover + render, from an already-approved script.

    Reuses utils/stock_videos.py, utils/audio.py, utils/video.py, utils/metadata.py
    exactly as main.py does today."""
    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.FETCHING_MEDIA, voice=voice or DEFAULT_VOICE)
    await progress("fetching_media", "Fetching stock footage...")
    stock_videos = await asyncio.to_thread(get_stock_videos, job["search_terms"])

    _check_cancel(should_cancel)
    await progress("fetching_media", "Generating voiceover...")
    voiceover_path = await asyncio.to_thread(
        generate_voiceover, job["script"], voice or DEFAULT_VOICE
    )

    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.RENDERING)
    await progress("rendering", "Rendering final video (this can take a minute or two)...")
    video_path, credits = await asyncio.to_thread(
        generate_video, stock_videos, voiceover_path, job["script"], job["search_terms"]
    )

    description = job["description"] or ""
    if credits:
        description = description + "\n\n" + "\n".join(credits)

    saved_path = await asyncio.to_thread(
        save_metadata,
        job["title"],
        description,
        None,
        job["script"],
        job["search_terms"],
        video_path,
    )

    update_job(
        job_id,
        stage=JobStage.RENDERED,
        video_path=str(saved_path),
        description=description,
    )
    await progress("rendered", "Video rendered successfully.")
    return {"video_path": str(saved_path)}


async def run_publish_stage(
    job_id: str, job: dict[str, Any], progress: ProgressCallback, should_cancel: ShouldCancel
) -> None:
    """Stage 3 (optional): upload to YouTube. Still respects NO_UPLOAD - auto_upload()
    itself no-ops when NO_UPLOAD=true, unchanged from main.py's behavior."""
    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.PUBLISHING)
    await progress("publishing", "Uploading to YouTube (no-op if NO_UPLOAD=true)...")

    await asyncio.to_thread(
        auto_upload, job["video_path"], job["title"], job["description"]
    )

    update_job(job_id, stage=JobStage.DONE)
    await progress("done", "Done.")
