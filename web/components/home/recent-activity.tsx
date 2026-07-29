"use client";

import Link from "next/link";
import { Sparkles, Video } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { JobStageBadge } from "@/components/common/job-stage-badge";
import { useJobs } from "@/lib/hooks/use-jobs";
import { formatRelativeTime } from "@/lib/utils";

export function RecentActivity() {
  const { data: jobs, isPending, isError } = useJobs();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent activity</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending && (
          <div className="space-y-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {isError && (
          <p className="text-sm text-destructive">
            Couldn&apos;t load recent jobs.
          </p>
        )}

        {jobs && jobs.length === 0 && (
          <EmptyState
            icon={Video}
            title="No videos generated yet"
            description="Start your first generation to see activity here."
            action={
              <Button asChild size="sm">
                <Link href="/generate">
                  <Sparkles /> New generation
                </Link>
              </Button>
            }
          />
        )}

        {jobs && jobs.length > 0 && (
          <ul className="divide-y">
            {jobs.slice(0, 8).map((job) => (
              <li
                key={job.id}
                className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {job.title ?? job.topic}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatRelativeTime(job.updated_at)}
                  </p>
                </div>
                <JobStageBadge stage={job.stage} />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
