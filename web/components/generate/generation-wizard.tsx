"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Loader2, RotateCcw, Square, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScriptEditor } from "@/components/generate/script-editor";
import { RenderProgress } from "@/components/generate/render-progress";
import { TopicPicker } from "@/components/generate/topic-picker";
import { VideoPreview } from "@/components/generate/video-preview";
import {
  useCancelJob,
  useContinueJob,
  useCreateJob,
  useJob,
  useUpdateScript,
} from "@/lib/hooks/use-jobs";
import type { JobResponse } from "@/lib/api/types";

function StepShell({
  stepKey,
  children,
}: {
  stepKey: string;
  children: React.ReactNode;
}) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={stepKey}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.2 }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

function GeneratingScriptState({
  job,
  onCancel,
  isCancelling,
}: {
  job: JobResponse;
  onCancel: () => void;
  isCancelling: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Writing your script...</p>
          <p className="text-sm text-muted-foreground">{job.topic}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onCancel} disabled={isCancelling}>
          <Square /> Cancel
        </Button>
      </CardContent>
    </Card>
  );
}

function FailedState({
  job,
  onStartOver,
}: {
  job: JobResponse;
  onStartOver: () => void;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="rounded-full bg-destructive/10 p-4">
          <AlertTriangle className="size-8 text-destructive" />
        </div>
        <div className="max-w-md space-y-1.5">
          <p className="text-sm font-medium">Generation failed</p>
          <p className="break-words text-sm text-muted-foreground">
            {job.error ?? "Unknown error."}
          </p>
        </div>
        <Button onClick={onStartOver}>
          <RotateCcw /> Try again
        </Button>
      </CardContent>
    </Card>
  );
}

function CancelledState({ onStartOver }: { onStartOver: () => void }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <XCircle className="size-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Generation cancelled.</p>
        <Button onClick={onStartOver}>
          <RotateCcw /> New generation
        </Button>
      </CardContent>
    </Card>
  );
}

type StepGroup =
  | "topic"
  | "generating"
  | "script"
  | "rendering"
  | "preview"
  | "failed"
  | "cancelled";

function getStepGroup(job: JobResponse | undefined): StepGroup {
  if (!job) return "topic";
  switch (job.stage) {
    case "pending":
    case "generating_script":
      return "generating";
    case "script_ready":
      return "script";
    case "fetching_media":
    case "rendering":
      return "rendering";
    case "rendered":
    case "publishing":
    case "done":
      return "preview";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
  }
}

export function GenerationWizard() {
  const [jobId, setJobId] = useState<string | null>(null);
  const { data: job } = useJob(jobId);
  const stepGroup = getStepGroup(job);

  const createJob = useCreateJob();
  const updateScript = useUpdateScript();
  const continueJob = useContinueJob();
  const cancelJob = useCancelJob();

  const handleGenerate = (topic: string) => {
    createJob.mutate(topic, {
      onSuccess: (created) => setJobId(created.id),
    });
  };

  const handleContinue = async (fields: {
    title: string;
    script: string;
    description: string;
    voice: string;
  }) => {
    if (!job) return;

    const dirty =
      fields.title !== job.title ||
      fields.script !== job.script ||
      fields.description !== job.description;

    if (dirty) {
      await updateScript.mutateAsync({
        id: job.id,
        fields: {
          title: fields.title,
          script: fields.script,
          description: fields.description,
        },
      });
    }

    continueJob.mutate({ id: job.id, voice: fields.voice || undefined });
  };

  const handleStartOver = () => setJobId(null);

  return (
    <div className="mx-auto max-w-xl">
      <StepShell stepKey={stepGroup}>
        {stepGroup === "topic" ? (
          <TopicPicker
            onGenerate={handleGenerate}
            isGenerating={createJob.isPending}
          />
        ) : !job ? null : stepGroup === "generating" ? (
          <GeneratingScriptState
            job={job}
            onCancel={() => cancelJob.mutate(job.id)}
            isCancelling={cancelJob.isPending}
          />
        ) : stepGroup === "script" ? (
          <ScriptEditor
            job={job}
            onContinue={handleContinue}
            isSaving={updateScript.isPending}
            isContinuing={continueJob.isPending}
          />
        ) : stepGroup === "rendering" ? (
          <RenderProgress job={job} />
        ) : stepGroup === "preview" ? (
          <VideoPreview job={job} onStartOver={handleStartOver} />
        ) : stepGroup === "failed" ? (
          <FailedState job={job} onStartOver={handleStartOver} />
        ) : (
          <CancelledState onStartOver={handleStartOver} />
        )}
      </StepShell>
    </div>
  );
}
