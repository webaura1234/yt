from pathlib import Path
from typing import Optional

import dotenv
from fastapi import APIRouter

import config
from api.schemas import ApiKeyStatus, SettingsResponse, SettingsUpdateRequest

router = APIRouter(tags=["settings"])

_ENV_PATH = Path(".env")

_SECRET_ENV_KEYS = {
    "gemini_api_key": "GEMINI_API_KEY",
    "openai_api_key": "OPENAI_API_KEY_AUTO_YT_SHORTS",
    "pexels_api_key": "PEXELS_API_KEY",
    "assembly_ai_api_key": "ASSEMBLY_AI_API_KEY",
    "news_api_key": "NEWS_API_KEY",
    "apprise_url": "APPRISE_URL",
}

_NON_SECRET_ENV_KEYS = {
    "gemini_text_model": "GEMINI_TEXT_MODEL",
    "openai_model": "OPENAI_MODEL",
    "cron_schedule": "CRON_SCHEDULE",
    "run_once": "RUN_ONCE",
    "video_count": "VIDEO_COUNT",
    "no_upload": "NO_UPLOAD",
    "notify_on_success": "NOTIFY_ON_SUCCESS",
}


def _mask(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


@router.get("/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return SettingsResponse(
        llm_provider_default="gemini",
        gemini_text_model=config.GEMINI_TEXT_MODEL,
        gemini_tts_model=config.GEMINI_TTS_MODEL,
        openai_model=config.OPENAI_MODEL,
        api_keys=ApiKeyStatus(
            gemini=bool(config.GEMINI_API_KEY),
            openai=bool(config.OPENAI_API_KEY),
            pexels=bool(config.PEXELS_API_KEY),
            assembly_ai=bool(config.ASSEMBLY_AI_API_KEY),
            news_api=bool(config.NEWS_API_KEY),
        ),
        api_key_previews={
            "gemini": _mask(config.GEMINI_API_KEY),
            "openai": _mask(config.OPENAI_API_KEY),
            "pexels": _mask(config.PEXELS_API_KEY),
            "assembly_ai": _mask(config.ASSEMBLY_AI_API_KEY),
            "news_api": _mask(config.NEWS_API_KEY),
        },
        cron_schedule=config.CRON_SCHEDULE,
        run_once=config.RUN_ONCE,
        video_count=config.VIDEO_COUNT,
        no_upload=config.NO_UPLOAD,
        notify_on_success=config.NOTIFY_ON_SUCCESS,
        apprise_url_set=bool(config.APPRISE_URL),
    )


@router.put("/settings")
def update_settings(payload: SettingsUpdateRequest) -> dict:
    """Writes changes to .env via python-dotenv (preserves existing formatting/comments
    instead of a naive rewrite). Secrets are write-only: never echoed back. Takes effect
    on next restart of the API/cron process - config.py loads once at import time, so
    this intentionally doesn't attempt in-process hot-reload."""
    updated_keys = []

    for field, env_key in _SECRET_ENV_KEYS.items():
        value = getattr(payload, field)
        if value:
            dotenv.set_key(str(_ENV_PATH), env_key, value)
            updated_keys.append(env_key)

    for field, env_key in _NON_SECRET_ENV_KEYS.items():
        value = getattr(payload, field)
        if value is not None:
            dotenv.set_key(str(_ENV_PATH), env_key, str(value))
            updated_keys.append(env_key)

    return {"updated_keys": updated_keys, "restart_required": bool(updated_keys)}
