"use client";

import { Clock, HardDrive, KeyRound, Video } from "lucide-react";

import { StatCard } from "@/components/common/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useStats } from "@/lib/hooks/use-system";
import { formatBytes } from "@/lib/utils";

export function SystemOverview() {
  const { data: stats, isPending, isError } = useStats();

  if (isPending) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <p className="text-sm text-destructive">
        Couldn&apos;t load system stats.
      </p>
    );
  }

  const keysConfigured = Object.values(stats.api_keys).filter(Boolean).length;
  const keysTotal = Object.keys(stats.api_keys).length;
  const mediaCacheBytes = stats.disk_usage.music_bytes + stats.disk_usage.secondary_video_bytes;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        icon={Video}
        label="Videos generated"
        value={String(stats.videos_generated_total)}
      />
      <StatCard
        icon={HardDrive}
        label="Media cache"
        value={formatBytes(mediaCacheBytes)}
        subLabel="music + stock footage"
      />
      <StatCard
        icon={KeyRound}
        label="API keys configured"
        value={`${keysConfigured}/${keysTotal}`}
      />
      <StatCard
        icon={Clock}
        label="Mode"
        value={stats.no_upload ? "Draft only" : "Auto-publish"}
        subLabel={stats.run_once ? "Run once" : stats.cron_schedule}
      />
    </div>
  );
}
