"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiKeyChecklist } from "@/components/common/api-key-checklist";
import { LogViewer } from "@/components/developer/log-viewer";
import { ManualRunPanel } from "@/components/developer/manual-run-panel";
import { RecentActivity } from "@/components/home/recent-activity";
import { useHealth, useStats } from "@/lib/hooks/use-system";
import { formatBytes } from "@/lib/utils";

function Diagnostics() {
  const { data: health } = useHealth();
  const { data: stats, isPending } = useStats();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Diagnostics</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPending || !stats ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Backend uptime</dt>
                <dd>{health ? `${Math.round(health.uptime_seconds)}s` : "-"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Cron schedule</dt>
                <dd className="font-mono">{stats.cron_schedule}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Music cache</dt>
                <dd>{formatBytes(stats.disk_usage.music_bytes)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Stock footage cache</dt>
                <dd>{formatBytes(stats.disk_usage.secondary_video_bytes)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Output size</dt>
                <dd>{formatBytes(stats.disk_usage.output_bytes)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Temp size</dt>
                <dd>{formatBytes(stats.disk_usage.temp_bytes)}</dd>
              </div>
            </dl>
            <div>
              <p className="mb-2 text-sm text-muted-foreground">API keys</p>
              <ApiKeyChecklist status={stats.api_keys} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function DeveloperPage() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ManualRunPanel />
        <Diagnostics />
      </div>
      <LogViewer />
      <RecentActivity />
    </div>
  );
}
