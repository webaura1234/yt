from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float


class ApiKeyStatus(BaseModel):
    gemini: bool
    openai: bool
    pexels: bool
    assembly_ai: bool
    news_api: bool


class DiskUsage(BaseModel):
    music_bytes: int
    secondary_video_bytes: int
    output_bytes: int
    temp_bytes: int


class YoutubeStatus(BaseModel):
    # "configured" = OAuth client secret is present; "authorized" = a token has
    # been issued (i.e. `python upload_video.py` has been run once already).
    configured: bool
    authorized: bool


class StatsResponse(BaseModel):
    api_keys: ApiKeyStatus
    youtube: YoutubeStatus
    disk_usage: DiskUsage
    cron_schedule: str
    run_once: bool
    video_count: int
    no_upload: bool
    notify_on_success: bool
    videos_generated_total: int


class TopicSuggestion(BaseModel):
    topic: str
    score: float
    times_used: int
    last_used_at: Optional[str] = None


class CustomTopicRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)


class SettingsResponse(BaseModel):
    llm_provider_default: str
    gemini_text_model: str
    gemini_tts_model: str
    openai_model: str
    api_keys: ApiKeyStatus
    api_key_previews: dict[str, Optional[str]]
    cron_schedule: str
    run_once: bool
    video_count: int
    no_upload: bool
    notify_on_success: bool
    apprise_url_set: bool


class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    assembly_ai_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    apprise_url: Optional[str] = None

    gemini_text_model: Optional[str] = None
    openai_model: Optional[str] = None

    cron_schedule: Optional[str] = None
    run_once: Optional[bool] = None
    video_count: Optional[int] = None
    no_upload: Optional[bool] = None
    notify_on_success: Optional[bool] = None


class LogsResponse(BaseModel):
    lines: list[str]


class JobResponse(BaseModel):
    id: str
    topic: str
    stage: str
    title: Optional[str] = None
    script: Optional[str] = None
    description: Optional[str] = None
    search_terms: Optional[list[str]] = None
    # The per-sentence shot plan: subject, action, location and the queries that
    # will be searched. Exposed so the dashboard can show what each scene is
    # going to look for while the job is paused for review.
    storyboard: Optional[list[dict]] = None
    voice: Optional[str] = None
    video_path: Optional[str] = None
    youtube_video_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class CreateJobRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)


class UpdateScriptRequest(BaseModel):
    title: Optional[str] = None
    script: Optional[str] = None
    description: Optional[str] = None
    search_terms: Optional[list[str]] = None


class SelectVoiceRequest(BaseModel):
    voice: str


class ContinueJobRequest(BaseModel):
    voice: Optional[str] = None


class VoiceOption(BaseModel):
    name: str
    verified: bool


class MediaItem(BaseModel):
    category: str
    filename: str
    size_bytes: int
    url: str
    license: Optional[str] = None
    credit: Optional[str] = None
    source_url: Optional[str] = None
    attribution_required: bool = False


class MediaListResponse(BaseModel):
    music: list[MediaItem]
    secondary_video: list[MediaItem]


class DedupeResponse(BaseModel):
    music_removed: int
    secondary_video_removed: int
