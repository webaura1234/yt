"use client";

import { CheckCircle2, Clock, Timer, Video } from "lucide-react";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "@/components/common/empty-state";
import { JobStageBadge } from "@/components/common/job-stage-badge";
import { StatCard } from "@/components/common/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobs } from "@/lib/hooks/use-jobs";
import { formatDuration, formatRelativeTime } from "@/lib/utils";
import type { JobResponse } from "@/lib/api/types";

const TERMINAL_STAGES = new Set<JobResponse["stage"]>(["done", "failed", "cancelled"]);
const DAYS_SHOWN = 14;

function dayKey(iso: string): string {
  return iso.slice(0, 10); // "YYYY-MM-DD"
}

function dayLabel(key: string): string {
  const [, month, day] = key.split("-");
  return `${Number(month)}/${Number(day)}`;
}

function buildDailyCounts(jobs: JobResponse[]) {
  const counts = new Map<string, number>();
  const today = new Date();
  for (let i = DAYS_SHOWN - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    counts.set(d.toISOString().slice(0, 10), 0);
  }

  for (const job of jobs) {
    const key = dayKey(job.created_at);
    if (counts.has(key)) {
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }

  return Array.from(counts.entries()).map(([key, count]) => ({
    date: dayLabel(key),
    count,
  }));
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      <p className="font-medium">{label}</p>
      <p className="text-muted-foreground">
        {payload[0].value} video{payload[0].value === 1 ? "" : "s"}
      </p>
    </div>
  );
}

export function AnalyticsDashboard() {
  const { data: jobs, isPending, isError } = useJobs();

  const stats = useMemo(() => {
    if (!jobs) return null;

    const terminal = jobs.filter((j) => TERMINAL_STAGES.has(j.stage));
    const done = jobs.filter((j) => j.stage === "done");
    const inProgress = jobs.length - terminal.length;

    const durations = done.map(
      (j) => new Date(j.updated_at).getTime() - new Date(j.created_at).getTime(),
    );
    const avgDurationMs =
      durations.length > 0
        ? durations.reduce((a, b) => a + b, 0) / durations.length
        : 0;

    const successRate = terminal.length > 0 ? done.length / terminal.length : 0;

    return {
      total: jobs.length,
      inProgress,
      successRate,
      avgDurationMs,
      daily: buildDailyCounts(jobs),
    };
  }, [jobs]);

  if (isPending) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <p className="text-sm text-destructive">
        Couldn&apos;t load generation history.
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Analytics</h2>
        <p className="text-sm text-muted-foreground">
          Generation history and timings from real job records. Views, CTR,
          watch-time, and retention will show up here once a channel has
          published and YouTube has accrued data.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Video} label="Total generations" value={String(stats.total)} />
        <StatCard
          icon={CheckCircle2}
          label="Success rate"
          value={`${Math.round(stats.successRate * 100)}%`}
          subLabel="of finished runs"
        />
        <StatCard
          icon={Timer}
          label="Avg. generation time"
          value={stats.avgDurationMs > 0 ? formatDuration(stats.avgDurationMs) : "—"}
        />
        <StatCard icon={Clock} label="In progress" value={String(stats.inProgress)} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Videos generated, last {DAYS_SHOWN} days</CardTitle>
        </CardHeader>
        <CardContent>
          {stats.total === 0 ? (
            <EmptyState
              icon={Video}
              title="No generations yet"
              description="Data will show up here once you generate a video."
            />
          ) : (
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.daily} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.5} />
                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                    stroke="var(--muted-foreground)"
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                    stroke="var(--muted-foreground)"
                    allowDecimals={false}
                    width={28}
                  />
                  <Tooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltip />} />
                  <Bar
                    dataKey="count"
                    fill="var(--color-chart-1)"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent generations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {jobs && jobs.length === 0 && (
            <EmptyState
              icon={Video}
              title="No generations yet"
              description="Start your first generation to see history here."
            />
          )}

          {jobs?.slice(0, 10).map((job) => {
            const durationMs = TERMINAL_STAGES.has(job.stage)
              ? new Date(job.updated_at).getTime() - new Date(job.created_at).getTime()
              : null;

            return (
              <div
                key={job.id}
                className="flex items-center justify-between gap-3 rounded-lg border p-3"
              >
                <div className="min-w-0 space-y-1">
                  <p className="truncate text-sm font-medium">
                    {job.title ?? job.topic}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatRelativeTime(job.created_at)}
                    {durationMs !== null && ` · took ${formatDuration(durationMs)}`}
                  </p>
                </div>
                <JobStageBadge stage={job.stage} />
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
