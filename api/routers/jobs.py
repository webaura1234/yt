import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.jobs import manager
from api.jobs.store import get_job, list_jobs, update_job
from api.schemas import (
    ContinueJobRequest,
    CreateJobRequest,
    JobResponse,
    SelectVoiceRequest,
    UpdateScriptRequest,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_or_404(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobResponse)
async def create_job(payload: CreateJobRequest) -> dict:
    return await manager.start_job(payload.topic.strip())


@router.get("", response_model=list[JobResponse])
def get_jobs() -> list[dict]:
    return list_jobs()


@router.get("/{job_id}", response_model=JobResponse)
def get_job_detail(job_id: str) -> dict:
    return _get_job_or_404(job_id)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    _get_job_or_404(job_id)

    async def event_generator():
        async for payload in manager.event_stream(job_id):
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.patch("/{job_id}/script", response_model=JobResponse)
def update_script(job_id: str, payload: UpdateScriptRequest) -> dict:
    job = _get_job_or_404(job_id)
    if job["stage"] != "script_ready":
        raise HTTPException(
            status_code=409,
            detail=f"Script can only be edited while paused at script_ready (current stage: {job['stage']})",
        )

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return job
    return update_job(job_id, **updates)


@router.post("/{job_id}/voice", response_model=JobResponse)
def select_voice(job_id: str, payload: SelectVoiceRequest) -> dict:
    _get_job_or_404(job_id)
    return update_job(job_id, voice=payload.voice)


@router.post("/{job_id}/continue", response_model=JobResponse)
async def continue_job(job_id: str, payload: ContinueJobRequest) -> dict:
    job = _get_job_or_404(job_id)
    # A voice explicitly passed to /continue wins; otherwise fall back to whatever was
    # previously chosen via POST /voice, rather than silently discarding that selection.
    voice = payload.voice or job.get("voice")
    try:
        return await manager.continue_job(job_id, voice=voice)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{job_id}/publish", response_model=JobResponse)
async def publish_job(job_id: str) -> dict:
    try:
        return await manager.publish_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str) -> dict:
    try:
        return await manager.cancel_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
