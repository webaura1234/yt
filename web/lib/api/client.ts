import type {
  HealthResponse,
  JobResponse,
  LogsResponse,
  SettingsResponse,
  SettingsUpdateRequest,
  StatsResponse,
  TopicSuggestion,
  VoiceOption,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON - fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  stats: () => request<StatsResponse>("/api/stats"),

  topics: () => request<TopicSuggestion[]>("/api/topics"),
  customTopic: (topic: string) =>
    request<TopicSuggestion>("/api/topics/custom", {
      method: "POST",
      body: JSON.stringify({ topic }),
    }),

  voices: () => request<VoiceOption[]>("/api/voices"),

  settings: () => request<SettingsResponse>("/api/settings"),
  updateSettings: (payload: SettingsUpdateRequest) =>
    request<{ updated_keys: string[]; restart_required: boolean }>(
      "/api/settings",
      { method: "PUT", body: JSON.stringify(payload) },
    ),

  logs: (tail = 200) => request<LogsResponse>(`/api/logs?tail=${tail}`),
  logsStreamUrl: () => `${API_BASE_URL}/api/logs/stream`,

  jobs: {
    list: () => request<JobResponse[]>("/api/jobs"),
    get: (id: string) => request<JobResponse>(`/api/jobs/${id}`),
    create: (topic: string) =>
      request<JobResponse>("/api/jobs", {
        method: "POST",
        body: JSON.stringify({ topic }),
      }),
    updateScript: (
      id: string,
      payload: Partial<
        Pick<JobResponse, "title" | "script" | "description" | "search_terms">
      >,
    ) =>
      request<JobResponse>(`/api/jobs/${id}/script`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    selectVoice: (id: string, voice: string) =>
      request<JobResponse>(`/api/jobs/${id}/voice`, {
        method: "POST",
        body: JSON.stringify({ voice }),
      }),
    continue: (id: string, voice?: string) =>
      request<JobResponse>(`/api/jobs/${id}/continue`, {
        method: "POST",
        body: JSON.stringify({ voice }),
      }),
    publish: (id: string) =>
      request<JobResponse>(`/api/jobs/${id}/publish`, { method: "POST" }),
    cancel: (id: string) =>
      request<JobResponse>(`/api/jobs/${id}/cancel`, { method: "POST" }),
    streamUrl: (id: string) => `${API_BASE_URL}/api/jobs/${id}/stream`,
  },

  media: {
    outputUrl: (path: string) => `${API_BASE_URL}/media/output/${path}`,
  },
};
