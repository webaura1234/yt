"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiConnectionBadge } from "@/components/common/api-connection-badge";
import { ApiKeyChecklist } from "@/components/common/api-key-checklist";
import { RecentActivity } from "@/components/home/recent-activity";
import { SystemOverview } from "@/components/home/system-overview";
import { useStats } from "@/lib/hooks/use-system";

export default function HomePage() {
  const { data: stats, isPending } = useStats();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ApiConnectionBadge />
        <Button asChild>
          <Link href="/generate">
            <Sparkles /> New generation
          </Link>
        </Button>
      </div>

      <SystemOverview />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecentActivity />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>API keys</CardTitle>
          </CardHeader>
          <CardContent>
            {isPending || !stats ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <ApiKeyChecklist status={stats.api_keys} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
