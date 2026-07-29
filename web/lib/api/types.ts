// Hand-typed to mirror api/schemas.py exactly - this is the contract between the two apps.

export interface ApiKeyStatus {
  gemini: boolean;
  openai: boolean;
  pexels: boolean;
  assembly_ai: boolean;
  news_api: boolean;
}

export interface HealthResponse {
  status: string;
  uptime_seconds: number;
}

export interface DiskUsage {
  music_bytes: number;
  secondary_video_bytes: number;
  output_bytes: number;
  temp_bytes: number;
}

export interface StatsResponse {
  api_keys: ApiKeyStatus;
  disk_usage: DiskUsage;
  cron_schedule: string;
  run_once: boolean;
  video_count: number;
  no_upload: boolean;
  notify_on_success: boolean;
  videos_generated_total: number;
}

export interface TopicSuggestion {
  topic: string;
  score: number;
  times_used: number;
  last_used_at: string | null;
}

export interface SettingsResponse {
  llm_provider_default: string;
  gemini_text_model: string;
  gemini_tts_model: string;
  openai_model: string;
  api_keys: ApiKeyStatus;
  api_key_previews: Record<string, string | null>;
  cron_schedule: string;
  run_once: boolean;
  video_count: number;
  no_upload: boolean;
  notify_on_success: boolean;
  apprise_url_set: boolean;
}

export interface SettingsUpdateRequest {
  gemini_api_key?: string;
  openai_api_key?: string;
  pexels_api_key?: string;
  assembly_ai_api_key?: string;
  news_api_key?: string;
  apprise_url?: string;
  gemini_text_model?: string;
  openai_model?: string;
  cron_schedule?: string;
  run_once?: boolean;
  video_count?: number;
  no_upload?: boolean;
  notify_on_success?: boolean;
}

export interface LogsResponse {
  lines: string[];
}

export type JobStage =
  | "pending"
  | "generating_script"
  | "script_ready"
  | "fetching_media"
  | "rendering"
  | "rendered"
  | "publishing"
  | "done"
  | "failed"
  | "cancelled";

export interface JobResponse {
  id: string;
  topic: string;
  stage: JobStage;
  title: string | null;
  script: string | null;
  description: string | null;
  search_terms: string[] | null;
  voice: string | null;
  video_path: string | null;
  youtube_video_id: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface VoiceOption {
  name: string;
  verified: boolean;
}

export interface JobEvent {
  event: string;
  message: string;
}

// Mirrors api/jobs/manager.py's _TERMINAL_EVENTS - the backend closes the SSE stream
// after one of these; the client must stop listening (not just wait for a
// reconnect) or the browser's EventSource will retry forever against a job that's
// already paused/finished.
export const JOB_TERMINAL_EVENTS = new Set([
  "done",
  "failed",
  "cancelled",
  "script_ready",
  "rendered",
]);

export interface LogLineEvent {
  line: string;
}
