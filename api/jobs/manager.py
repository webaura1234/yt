import asyncio
import logging
from typing import Any, AsyncIterator, Optional

from api.jobs import pipeline
from api.jobs.store import JobStage, create_job, get_job, update_job

logger = logging.getLogger(__name__)

# Fan-out pub/sub, not one long-lived queue per job: each /stream connection gets its
# own fresh queue and only sees events emitted *after* it subscribed. A job's full
# lifecycle spans multiple separate stream connections (one per phase - script
# generation, then render, then publish), so a shared single queue would replay stale
# backlog (including old terminal markers) to whichever phase connects next. Current
# job state is always available via GET /api/jobs/{id} regardless of stream timing.
_subscribers: dict[str, list["asyncio.Queue[dict]"]] = {}
_cancelled: set[str] = set()

# Events that end a stream connection: either the job paused waiting for user input
# (script_ready, rendered) or reached a true terminal state (done/failed/cancelled).
_TERMINAL_EVENTS = {"done", "failed", "cancelled", "script_ready", "rendered"}


def _subscribe(job_id: str) -> "asyncio.Queue[dict]":
    queue: "asyncio.Queue[dict]" = asyncio.Queue()
    _subscribers.setdefault(job_id, []).append(queue)
    return queue


def _unsubscribe(job_id: str, queue: "asyncio.Queue[dict]") -> None:
    subscribers = _subscribers.get(job_id, [])
    if queue in subscribers:
        subscribers.remove(queue)
    if not subscribers:
        _subscribers.pop(job_id, None)


async def _emit(job_id: str, event: str, message: str) -> None:
    payload = {"event": event, "message": message}
    for queue in _subscribers.get(job_id, []):
        await queue.put(payload)


def _is_cancelled(job_id: str) -> bool:
    return job_id in _cancelled


async def _run_script_stage(job_id: str, topic: str) -> None:
    try:
        await pipeline.run_script_stage(
            job_id, topic, lambda e, m: _emit(job_id, e, m), lambda: _is_cancelled(job_id)
        )
    except pipeline.JobCancelled:
        update_job(job_id, stage=JobStage.CANCELLED)
        await _emit(job_id, "cancelled", "Job cancelled.")
    except Exception as e:
        logger.exception(f"Job {job_id} failed during script generation")
        update_job(job_id, stage=JobStage.FAILED, error=str(e))
        await _emit(job_id, "failed", str(e))


async def _run_render_stage(job_id: str, voice: Optional[str]) -> None:
    job = get_job(job_id)
    try:
        await pipeline.run_render_stage(
            job_id, job, voice, lambda e, m: _emit(job_id, e, m), lambda: _is_cancelled(job_id)
        )
    except pipeline.JobCancelled:
        update_job(job_id, stage=JobStage.CANCELLED)
        await _emit(job_id, "cancelled", "Job cancelled.")
    except Exception as e:
        logger.exception(f"Job {job_id} failed during render")
        update_job(job_id, stage=JobStage.FAILED, error=str(e))
        await _emit(job_id, "failed", str(e))


async def _run_publish_stage(job_id: str) -> None:
    job = get_job(job_id)
    try:
        await pipeline.run_publish_stage(
            job_id, job, lambda e, m: _emit(job_id, e, m), lambda: _is_cancelled(job_id)
        )
    except pipeline.JobCancelled:
        update_job(job_id, stage=JobStage.CANCELLED)
        await _emit(job_id, "cancelled", "Job cancelled.")
    except Exception as e:
        logger.exception(f"Job {job_id} failed during publish")
        update_job(job_id, stage=JobStage.FAILED, error=str(e))
        await _emit(job_id, "failed", str(e))


async def start_job(topic: str) -> dict[str, Any]:
    # NOTE: this must be called from a route handler that's itself `async def` -
    # asyncio.create_task() requires a running event loop in the current thread, and
    # FastAPI dispatches plain `def` handlers to a worker thread with no event loop.
    job = create_job(topic)
    asyncio.create_task(_run_script_stage(job["id"], topic))
    return job


async def continue_job(job_id: str, voice: Optional[str] = None) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise ValueError("job not found")
    if job["stage"] != JobStage.SCRIPT_READY.value:
        raise ValueError(f"job is not ready to continue (stage={job['stage']})")
    asyncio.create_task(_run_render_stage(job_id, voice))
    return job


async def publish_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise ValueError("job not found")
    if job["stage"] != JobStage.RENDERED.value:
        raise ValueError(f"job is not rendered yet (stage={job['stage']})")
    asyncio.create_task(_run_publish_stage(job_id))
    return job


async def cancel_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise ValueError("job not found")
    _cancelled.add(job_id)
    # If nothing is actively running (job is sitting paused at script_ready), there's no
    # in-flight stage to cooperatively cancel - mark it cancelled immediately.
    if job["stage"] in (JobStage.SCRIPT_READY.value, JobStage.PENDING.value):
        return update_job(job_id, stage=JobStage.CANCELLED)
    return job


_STAGE_TO_TERMINAL_EVENT = {
    JobStage.SCRIPT_READY.value: "script_ready",
    JobStage.RENDERED.value: "rendered",
    JobStage.DONE.value: "done",
    JobStage.FAILED.value: "failed",
    JobStage.CANCELLED.value: "cancelled",
}


async def event_stream(job_id: str) -> AsyncIterator[dict]:
    job = get_job(job_id)
    if job and job["stage"] in _STAGE_TO_TERMINAL_EVENT:
        # The job already reached a pause/terminal point before this connection was
        # made (e.g. publish is near-instant when NO_UPLOAD=true) - reflect current
        # state immediately rather than waiting on a queue that will never receive an
        # event nobody was subscribed to hear.
        event = _STAGE_TO_TERMINAL_EVENT[job["stage"]]
        message = job.get("error") or f"Job is at stage: {job['stage']}"
        yield {"event": event, "message": message}
        return

    queue = _subscribe(job_id)
    try:
        while True:
            payload = await queue.get()
            yield payload
            if payload["event"] in _TERMINAL_EVENTS:
                break
    finally:
        _unsubscribe(job_id, queue)
