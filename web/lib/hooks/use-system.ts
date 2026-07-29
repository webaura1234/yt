"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15_000,
    refetchIntervalInBackground: true,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
  });
}

export function useLogs(tail = 200) {
  return useQuery({
    queryKey: ["logs", tail],
    queryFn: () => api.logs(tail),
  });
}
