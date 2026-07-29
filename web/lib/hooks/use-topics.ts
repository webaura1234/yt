"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: api.topics,
  });
}

export function useCustomTopic() {
  return useMutation({
    mutationFn: (topic: string) => api.customTopic(topic),
  });
}

export function useVoices() {
  return useQuery({
    queryKey: ["voices"],
    queryFn: api.voices,
  });
}
