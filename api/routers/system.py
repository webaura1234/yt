import time
from pathlib import Path

from fastapi import APIRouter

import config
from api.schemas import ApiKeyStatus, DiskUsage, HealthResponse, StatsResponse

router = APIRouter(tags=["system"])

_start_time = time.monotonic()


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _api_key_status() -> ApiKeyStatus:
    return ApiKeyStatus(
        gemini=bool(config.GEMINI_API_KEY),
        openai=bool(config.OPENAI_API_KEY),
        pexels=bool(config.PEXELS_API_KEY),
        assembly_ai=bool(config.ASSEMBLY_AI_API_KEY),
        news_api=bool(config.NEWS_API_KEY),
    )


def _videos_generated_total() -> int:
    if not config.OUTPUT_PATH.exists():
        return 0
    return len(list(config.OUTPUT_PATH.glob("*/*.json")))


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", uptime_seconds=time.monotonic() - _start_time)


@router.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    return StatsResponse(
        api_keys=_api_key_status(),
        disk_usage=DiskUsage(
            music_bytes=_dir_size_bytes(config.BACKGROUND_SONGS_PATH),
            secondary_video_bytes=_dir_size_bytes(config.SECONDARY_CONTENT_PATH),
            output_bytes=_dir_size_bytes(config.OUTPUT_PATH),
            temp_bytes=_dir_size_bytes(config.TEMP_PATH),
        ),
        cron_schedule=config.CRON_SCHEDULE,
        run_once=config.RUN_ONCE,
        video_count=config.VIDEO_COUNT,
        no_upload=config.NO_UPLOAD,
        notify_on_success=config.NOTIFY_ON_SUCCESS,
        videos_generated_total=_videos_generated_total(),
    )
