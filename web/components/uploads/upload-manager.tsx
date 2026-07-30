"use client";

import {
  CheckCircle2,
  Clock,
  ExternalLink,
  Loader2,
  Upload as UploadIcon,
  XCircle,
} from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { JobStageBadge } from "@/components/common/job-stage-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { usePublishJob, useJobs } from "@/lib/hooks/use-jobs";
import { useStats } from "@/lib/hooks/use-system";
import { formatRelativeTime } from "@/lib/utils";
import type { JobResponse } from "@/lib/api/types";

// Jobs that have reached a render, so there's something to publish/have published.
const PUBLISHABLE_STAGES = new Set<JobResponse["stage"]>([
  "rendered",
  "publishing",
  "done",
  "failed",
]);

function YoutubeConnectionCard() {
  const { data: stats, isPending } = useStats();

  if (isPending) return <Skeleton className="h-20 w-full" />;
  if (!stats) return null;

  const { configured, authorized } = stats.youtube;
  const label = authorized
    ? "Connected"
    : configured
      ? "Not authorized yet"
      : "Not configured";
  const Icon = authorized ? CheckCircle2 : configured ? Clock : XCircle;
  const className = authorized
    ? "text-emerald-600 dark:text-emerald-400"
    : configured
      ? "text-amber-600 dark:text-amber-400"
      : "text-muted-foreground";

  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Icon className={className} />
          <div>
            <p className="text-sm font-medium">YouTube connection</p>
            <p className="text-xs text-muted-foreground">
              {authorized
                ? "OAuth token present - auto-publish is available."
                : configured
                  ? "Client secret found, but no token yet - run `python upload_video.py` once to authorize."
                  : "No credentials/client_secrets.json - uploads will stay in draft mode."}
            </p>
          </div>
        </div>
        <Badge variant="secondary" className={className}>
          {label}
        </Badge>
      </CardContent>
    </Card>
  );
}

function ScheduleCard() {
  const { data: stats, isPending } = useStats();

  if (isPending) return <Skeleton className="h-20 w-full" />;
  if (!stats) return null;

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <div>
          <span className="text-muted-foreground">Mode: </span>
          {stats.run_once ? "Run once" : `Cron (${stats.cron_schedule})`}
        </div>
        <div>
          <span className="text-muted-foreground">Videos per run: </span>
          {stats.video_count}
        </div>
        <div>
          <span className="text-muted-foreground">Uploads: </span>
          {stats.no_upload ? "Disabled (draft only)" : "Enabled"}
        </div>
      </CardContent>
    </Card>
  );
}

function PublishRow({ job }: { job: JobResponse }) {
  const publishJob = usePublishJob();
  const videoUrl = job.video_path ? api.media.outputUrl(job.video_path) : null;
  const isPublishing = job.stage === "publishing" || publishJob.isPending;

  return (
    <div className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 space-y-1">
        <p className="truncate text-sm font-medium">{job.title ?? job.topic}</p>
        <p className="text-xs text-muted-foreground">
          {formatRelativeTime(job.updated_at)}
          {job.error && job.stage === "failed" && (
            <span className="text-destructive"> · {job.error}</span>
          )}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
        <JobStageBadge stage={job.stage} />
        {videoUrl && (
          <Button variant="ghost" size="sm" asChild>
            <a href={videoUrl} target="_blank" rel="noreferrer">
              Preview
            </a>
          </Button>
        )}
        {job.youtube_video_id && (
          <Button variant="ghost" size="sm" asChild>
            <a
              href={`https://youtube.com/watch?v=${job.youtube_video_id}`}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink /> YouTube
            </a>
          </Button>
        )}
        {job.stage === "rendered" && (
          <Button
            size="sm"
            onClick={() => publishJob.mutate(job.id)}
            disabled={isPublishing}
          >
            {isPublishing ? (
              <Loader2 className="animate-spin" />
            ) : (
              <UploadIcon />
            )}
            Publish
          </Button>
        )}
      </div>
    </div>
  );
}

export function UploadManager() {
  const { data: jobs, isPending, isError } = useJobs();
  const { data: stats } = useStats();

  const publishable = (jobs ?? []).filter((j) => PUBLISHABLE_STAGES.has(j.stage));

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Upload manager</h2>
        <p className="text-sm text-muted-foreground">
          Publish history, YouTube connection status, and the current
          scheduling configuration.
        </p>
      </div>

      {stats?.no_upload && (
        <Alert>
          <AlertDescription>
            Uploads are currently disabled (<code>NO_UPLOAD=true</code>) -
            publishing will complete jobs without actually posting to
            YouTube. Change this in Settings once you&apos;re ready to go
            live.
          </AlertDescription>
        </Alert>
      )}

      <YoutubeConnectionCard />
      <ScheduleCard />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Publish history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {isPending &&
            Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}

          {isError && (
            <p className="text-sm text-destructive">Couldn&apos;t load jobs.</p>
          )}

          {!isPending && publishable.length === 0 && (
            <EmptyState
              icon={UploadIcon}
              title="Nothing to publish yet"
              description="Rendered videos will show up here once a generation completes."
            />
          )}

          {publishable.map((job) => (
            <PublishRow key={job.id} job={job} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
