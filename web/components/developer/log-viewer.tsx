"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Radio } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useEventSource } from "@/lib/hooks/use-event-source";
import { useLogs } from "@/lib/hooks/use-system";
import type { LogLineEvent } from "@/lib/api/types";

export function LogViewer() {
  const { data, isPending, isError } = useLogs(200);
  const [liveLines, setLiveLines] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const onMessage = useCallback((data: LogLineEvent) => {
    setLiveLines((prev) => [...prev, data.line].slice(-500));
  }, []);

  useEventSource<LogLineEvent>(api.logsStreamUrl(), onMessage, {
    onOpen: () => setConnected(true),
    onError: () => setConnected(false),
  });

  const allLines = [...(data?.lines ?? []), ...liveLines];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [allLines.length]);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Application logs</CardTitle>
        <Badge
          variant="outline"
          className={
            connected
              ? "gap-1.5 border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
              : "gap-1.5 text-muted-foreground"
          }
        >
          <Radio className="size-3" />
          {connected ? "Live" : "Connecting..."}
        </Badge>
      </CardHeader>
      <CardContent>
        {isPending && <Skeleton className="h-64 w-full" />}
        {isError && (
          <p className="text-sm text-destructive">Couldn&apos;t load logs.</p>
        )}
        {!isPending && !isError && (
          <div
            ref={scrollRef}
            className="h-64 overflow-y-auto rounded-md bg-muted/50 p-3 font-mono text-xs"
          >
            {allLines.length === 0 ? (
              <p className="text-muted-foreground">No log entries yet.</p>
            ) : (
              allLines.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap break-all">
                  {line}
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
