"use client";

import { CircleAlert, CircleCheck, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useHealth } from "@/lib/hooks/use-system";

export function ApiConnectionBadge() {
  const { data, isPending, isError } = useHealth();

  if (isPending) {
    return (
      <Badge variant="secondary" className="gap-1.5">
        <Loader2 className="size-3 animate-spin" />
        Checking backend...
      </Badge>
    );
  }

  if (isError || data?.status !== "ok") {
    return (
      <Badge variant="destructive" className="gap-1.5">
        <CircleAlert className="size-3" />
        Backend unreachable
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className="gap-1.5 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
    >
      <CircleCheck className="size-3" />
      Backend connected · uptime {Math.round(data.uptime_seconds)}s
    </Badge>
  );
}
