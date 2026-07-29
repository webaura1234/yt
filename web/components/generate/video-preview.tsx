"use client";

import { CheckCircle2, Download, Loader2, RotateCcw, Upload } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { usePublishJob } from "@/lib/hooks/use-jobs";
import { useStats } from "@/lib/hooks/use-system";
import type { JobResponse } from "@/lib/api/types";

export function VideoPreview({
  job,
  onStartOver,
}: {
  job: JobResponse;
  onStartOver: () => void;
}) {
  const { data: stats } = useStats();
  const publishJob = usePublishJob();

  const videoUrl = job.video_path ? api.media.outputUrl(job.video_path) : null;
  const isDone = job.stage === "done";
  const isPublishing = job.stage === "publishing" || publishJob.isPending;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{job.title}</CardTitle>
        <CardDescription>
          {isDone
            ? "Published"
            : isPublishing
              ? "Publishing..."
              : "Rendered — ready to publish"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {videoUrl && (
          // Captions are burned into the video itself during render, not a separate track.
          <video
            controls
            className="mx-auto max-h-[480px] w-full max-w-[270px] rounded-lg bg-black"
            src={videoUrl}
          />
        )}

        {job.description && (
          <div className="rounded-md bg-muted/50 p-3">
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">
              {job.description}
            </p>
          </div>
        )}

        {stats?.no_upload && !isDone && !isPublishing && (
          <Alert>
            <AlertDescription>
              Uploads are currently disabled (<code>NO_UPLOAD=true</code>) —
              publishing will complete the job without actually posting to
              YouTube. Change this in Settings once you&apos;re ready to go live.
            </AlertDescription>
          </Alert>
        )}

        {isDone && (
          <Alert className="border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-4" />
            <AlertDescription className="text-emerald-600 dark:text-emerald-400">
              {job.youtube_video_id
                ? `Published to YouTube (${job.youtube_video_id}).`
                : "Marked done. No real upload occurred (NO_UPLOAD=true)."}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        {videoUrl && (
          <Button variant="outline" asChild>
            <a href={videoUrl} download>
              <Download /> Download
            </a>
          </Button>
        )}
        {!isDone && (
          <Button
            onClick={() => publishJob.mutate(job.id)}
            disabled={isPublishing}
          >
            {isPublishing ? <Loader2 className="animate-spin" /> : <Upload />}
            Publish
          </Button>
        )}
        <Button variant="ghost" onClick={onStartOver} className="ml-auto">
          <RotateCcw /> New generation
        </Button>
      </CardFooter>
    </Card>
  );
}
