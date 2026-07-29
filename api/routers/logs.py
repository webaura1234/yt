import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from api.schemas import LogsResponse
from logging_setup import LOG_FILE

router = APIRouter(tags=["logs"])


def _tail_lines(n: int) -> list[str]:
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, "r", errors="replace") as f:
        lines = f.readlines()
    return [line.rstrip("\n") for line in lines[-n:]]


@router.get("/logs", response_model=LogsResponse)
def get_logs(tail: int = Query(200, ge=1, le=5000)) -> LogsResponse:
    return LogsResponse(lines=_tail_lines(tail))


@router.get("/logs/stream")
async def stream_logs():
    async def event_generator():
        position = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
        while True:
            await asyncio.sleep(1.0)
            if not LOG_FILE.exists():
                continue
            size = LOG_FILE.stat().st_size
            if size < position:
                # File rotated/truncated - restart from the beginning
                position = 0
            if size > position:
                with open(LOG_FILE, "r", errors="replace") as f:
                    f.seek(position)
                    new_content = f.read()
                    position = f.tell()
                for line in new_content.splitlines():
                    yield f"data: {json.dumps({'line': line})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
