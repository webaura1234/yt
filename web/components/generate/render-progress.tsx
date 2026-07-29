"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { useCallback, useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useEventSource } from "@/lib/hooks/use-event-source";
import { JOB_TERMINAL_EVENTS, type JobEvent, type JobResponse } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STEPS = [
  { key: "fetching_media", label: "Fetching stock footage & voice" },
  { key: "rendering", label: "Rendering video" },
];

export function RenderProgress({ job }: { job: JobResponse }) {
  const [messages, setMessages] = useState<JobEvent[]>([]);

  const onMessage = useCallback((event: JobEvent) => {
    setMessages((prev) => [...prev, event]);
  }, []);

  useEventSource<JobEvent>(api.jobs.streamUrl(job.id), onMessage, {
    stopOn: (event) => JOB_TERMINAL_EVENTS.has(event.event),
  });

  const latestMessage = messages.at(-1)?.message ?? "Starting render...";
  const currentStepIndex = STEPS.findIndex((s) => s.key === job.stage);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rendering your video</CardTitle>
        <CardDescription className="truncate">{job.title}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          {STEPS.map((step, i) => {
            const isDone = currentStepIndex > i || job.stage === "rendered";
            const isActive = currentStepIndex === i && !isDone;

            return (
              <div key={step.key} className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full border transition-colors",
                    isDone && "border-emerald-500 bg-emerald-500 text-white",
                    isActive && "border-primary",
                  )}
                >
                  {isDone ? (
                    <Check className="size-3.5" />
                  ) : isActive ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : null}
                </div>
                <span
                  className={cn(
                    "text-sm",
                    !isActive && !isDone && "text-muted-foreground",
                  )}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>

        <div className="rounded-md bg-muted/50 p-3">
          <AnimatePresence mode="wait">
            <motion.p
              key={latestMessage}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="text-sm text-muted-foreground"
            >
              {latestMessage}
            </motion.p>
          </AnimatePresence>
        </div>
      </CardContent>
    </Card>
  );
}
