"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { MediaCategory } from "@/lib/api/types";

export function useMediaList() {
  return useQuery({
    queryKey: ["media"],
    queryFn: api.media.list,
  });
}

export function useDedupeMedia() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.media.dedupe,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
    },
  });
}

export function useDeleteMedia() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ category, filename }: { category: MediaCategory; filename: string }) =>
      api.media.delete(category, filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
    },
  });
}
