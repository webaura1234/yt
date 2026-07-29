"use client";

import { useCallback, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { JobStageBadge } from "@/components/common/job-stage-badge";
import { api } from "@/lib/api/client";
import { useEventSource } from "@/lib/hooks/use-event-source";
import { useCancelJob, useCreateJob, useJob } from "@/lib/hooks/use-jobs";
import { JOB_TERMINAL_EVENTS, type JobEvent } from "@/lib/api/types";

const CANCELLABLE_STAGES = new Set([
  "pending",
  "generating_script",
  "script_ready",
  "fetching_media",
  "rendering",
]);

export function ManualRunPanel() {
  const [topic, setTopic] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);

  const createJob = useCreateJob();
  const cancelJob = useCancelJob();
  const { data: job } = useJob(jobId);

  const streamUrl = jobId ? api.jobs.streamUrl(jobId) : null;

  const onMessage = useCallback((event: JobEvent) => {
    setEvents((prev) => [...prev, event]);
  }, []);

  useEventSource<JobEvent>(streamUrl, onMessage, {
    stopOn: (event) => JOB_TERMINAL_EVENTS.has(event.event),
  });

  const handleStart = () => {
    if (!topic.trim()) return;
    setEvents([]);
    createJob.mutate(topic.trim(), {
      onSuccess: (created) => setJobId(created.id),
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manual pipeline execution</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Topic, e.g. Controversial Historical Mysteries"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleStart()}
            disabled={createJob.isPending}
          />
          <Button
            onClick={handleStart}
            disabled={!topic.trim() || createJob.isPending}
          >
            {createJob.isPending ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Play />
            )}
            Run
          </Button>
        </div>

        {job && (
          <div className="space-y-3 rounded-md border p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {job.title ?? job.topic}
                </p>
                <p className="font-mono text-xs text-muted-foreground">
                  {job.id}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <JobStageBadge stage={job.stage} />
                {CANCELLABLE_STAGES.has(job.stage) && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => cancelJob.mutate(job.id)}
                    disabled={cancelJob.isPending}
                  >
                    <Square /> Cancel
                  </Button>
                )}
              </div>
            </div>

            <div className="h-40 overflow-y-auto rounded-md bg-muted/50 p-3 font-mono text-xs">
              {events.length === 0 ? (
                <p className="text-muted-foreground">
                  Waiting for pipeline events...
                </p>
              ) : (
                events.map((e, i) => (
                  <div key={i}>
                    <span className="text-muted-foreground">[{e.event}]</span>{" "}
                    {e.message}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
