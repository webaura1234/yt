"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { JobResponse } from "@/lib/api/types";

type ScriptFields = Partial<
  Pick<JobResponse, "title" | "script" | "description" | "search_terms">
>;

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs.list,
    refetchInterval: 5_000,
    // Without this, polling silently pauses whenever the tab isn't the visible one
    // (Page Visibility API) - a job can finish while the user is on another tab and
    // the list would just sit stale until they click back. Job status polling should
    // keep going regardless of tab visibility.
    refetchIntervalInBackground: true,
  });
}

const TERMINAL_STAGES = new Set(["done", "failed", "cancelled"]);

export function useJob(id: string | null) {
  return useQuery({
    queryKey: ["jobs", id],
    queryFn: () => api.jobs.get(id as string),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data && TERMINAL_STAGES.has(query.state.data.stage)
        ? false
        : 2_000,
    refetchIntervalInBackground: true,
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (topic: string) => api.jobs.create(topic),
    onSuccess: (job: JobResponse) => {
      queryClient.setQueryData(["jobs", job.id], job);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.jobs.cancel(id),
    onSuccess: (job: JobResponse) => {
      queryClient.setQueryData(["jobs", job.id], job);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useUpdateScript() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, fields }: { id: string; fields: ScriptFields }) =>
      api.jobs.updateScript(id, fields),
    onSuccess: (job: JobResponse) => {
      queryClient.setQueryData(["jobs", job.id], job);
    },
  });
}

export function useSelectVoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, voice }: { id: string; voice: string }) =>
      api.jobs.selectVoice(id, voice),
    onSuccess: (job: JobResponse) => {
      queryClient.setQueryData(["jobs", job.id], job);
    },
  });
}

export function useContinueJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, voice }: { id: string; voice?: string }) =>
      api.jobs.continue(id, voice),
    onSuccess: (job: JobResponse) => {
      queryClient.setQueryData(["jobs", job.id], job);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function usePublishJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.jobs.publish(id),
    onSuccess: (job: JobResponse) => {
      queryClient.setQueryData(["jobs", job.id], job);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
