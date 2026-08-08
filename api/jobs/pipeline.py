import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from api.jobs.store import JobStage, update_job
from utils.audio import DEFAULT_VOICE, generate_voiceover
from utils.llm import (
    _generate,
    get_description,
    get_most_engaging_titles,
    get_script,
    get_titles,
)
from utils.metadata import save_metadata
from utils.storyboard import SceneBrief, brief_rows, build_storyboard, storyboard_table
from utils.video import generate_video
from utils.visual_director import direct_scenes, framing_report, unresolved_scenes
from utils.yt import auto_upload

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], Awaitable[None]]
ShouldCancel = Callable[[], bool]


class JobCancelled(Exception):
    pass


def _check_cancel(should_cancel: ShouldCancel) -> None:
    if should_cancel():
        raise JobCancelled()


def _briefs_for(job: dict[str, Any]) -> list[SceneBrief]:
    """The storyboard for a job, rebuilding it if the job predates storyboards.

    Jobs created before this stage existed only stored flat search strings. They
    are turned into minimal briefs from the script rather than being refused:
    a job paused at script_ready before a deploy should still be renderable
    afterwards, and a brief built from the sentence is what the storyboard
    module already falls back to when analysis fails.
    """
    stored = job.get("storyboard")
    if stored:
        return [SceneBrief.from_dict(entry) for entry in stored]

    logger.info("Job has no stored storyboard (created before storyboards); rebuilding it")
    return build_storyboard(job.get("title") or "", job.get("script") or "", generate=_generate)


async def run_script_stage(
    job_id: str, topic: str, progress: ProgressCallback, should_cancel: ShouldCancel
) -> None:
    """Stage 1: topic -> titles -> script -> description -> storyboard, then pause.

    Runs the same stages as main.py. The storyboard is built here, not at render
    time, so the shot plan is reviewable while the job is paused - which is the
    point of pausing."""
    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.GENERATING_SCRIPT)
    await progress("generating_script", "Generating title ideas...")

    titles = await asyncio.to_thread(get_titles, topic)
    best_titles = await asyncio.to_thread(get_most_engaging_titles, titles, 1)
    title = best_titles[0] if best_titles else topic

    _check_cancel(should_cancel)
    await progress("generating_script", f'Writing script for: "{title}"')
    script = await asyncio.to_thread(get_script, title, topic)

    _check_cancel(should_cancel)
    await progress("generating_script", "Writing description...")
    description = await asyncio.to_thread(get_description, title, script)

    _check_cancel(should_cancel)
    await progress("generating_script", "Storyboarding every line...")
    briefs = await asyncio.to_thread(build_storyboard, title, script, _generate)

    update_job(
        job_id,
        stage=JobStage.SCRIPT_READY,
        title=title,
        script=script,
        description=description,
        storyboard=[brief.to_dict() for brief in briefs],
        # Kept populated for the existing UI and for jobs listing: the first
        # query of each scene, which is what "search terms" now means.
        search_terms=[brief.queries[0] for brief in briefs if brief.queries],
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

    Rebuilds the storyboard briefs persisted by stage 1, then runs the full
    visual-director loop - multi-query search, scoring, framing, editor review,
    re-search on rejection - exactly as main.py does.

    Only the briefs cross the stage boundary. The chosen clips are found and
    consumed inside this function, so nothing about a SceneSelection has to be
    serialisable."""
    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.FETCHING_MEDIA, voice=voice or DEFAULT_VOICE)
    await progress("fetching_media", "Storyboarding and selecting footage...")
    briefs = _briefs_for(job)
    selections = await asyncio.to_thread(direct_scenes, briefs)

    # The storyboard table reaches the dashboard before rendering starts, so the
    # shot choices are visible while they are still cheap to change.
    table = storyboard_table(brief_rows(briefs, [s.table_row() for s in selections]))
    logger.info("Storyboard for job %s:\n%s\n%s", job_id, table, framing_report(selections))

    weak = unresolved_scenes(selections)
    if weak:
        await progress(
            "fetching_media",
            f"{len(weak)} of {len(selections)} scenes found no footage matching "
            "their narration - see the storyboard in the logs",
        )
    if not any(s.resolved for s in selections):
        raise RuntimeError(
            "No scene found footage that represents its narration; refusing to "
            "render. Check the storyboard in the logs for why each was rejected."
        )

    _check_cancel(should_cancel)
    await progress("fetching_media", "Generating voiceover...")
    voiceover_path = await asyncio.to_thread(
        generate_voiceover, job["script"], voice or DEFAULT_VOICE
    )

    _check_cancel(should_cancel)
    update_job(job_id, stage=JobStage.RENDERING)
    await progress("rendering", "Rendering final video (this can take a minute or two)...")
    video_path, credits = await asyncio.to_thread(
        generate_video, selections, voiceover_path, job["script"], job["search_terms"]
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
