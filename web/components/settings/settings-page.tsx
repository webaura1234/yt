"use client";

import { AlertTriangle, KeyRound, Loader2, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useSettings, useUpdateSettings } from "@/lib/hooks/use-settings";
import type { ApiKeyStatus, SettingsUpdateRequest } from "@/lib/api/types";

type ApiKeyField =
  | "gemini_api_key"
  | "openai_api_key"
  | "pexels_api_key"
  | "assembly_ai_api_key"
  | "news_api_key";

const API_KEY_FIELDS: {
  key: keyof ApiKeyStatus;
  field: ApiKeyField;
  label: string;
  required?: boolean;
}[] = [
  { key: "gemini", field: "gemini_api_key", label: "Gemini API key", required: true },
  { key: "openai", field: "openai_api_key", label: "OpenAI API key (fallback)" },
  { key: "pexels", field: "pexels_api_key", label: "Pexels API key" },
  { key: "assembly_ai", field: "assembly_ai_api_key", label: "AssemblyAI API key" },
  { key: "news_api", field: "news_api_key", label: "News API key" },
];

function BoolSelect({
  value,
  onChange,
  trueLabel,
  falseLabel,
}: {
  value: boolean;
  onChange: (value: boolean) => void;
  trueLabel: string;
  falseLabel: string;
}) {
  return (
    <Select value={String(value)} onValueChange={(v) => onChange(v === "true")}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="true">{trueLabel}</SelectItem>
        <SelectItem value="false">{falseLabel}</SelectItem>
      </SelectContent>
    </Select>
  );
}

export function SettingsManager() {
  const { data: settings, isPending, isError } = useSettings();
  const updateSettings = useUpdateSettings();

  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({});
  const [appriseUrl, setAppriseUrl] = useState("");
  const [geminiTextModel, setGeminiTextModel] = useState<string | null>(null);
  const [openaiModel, setOpenaiModel] = useState<string | null>(null);
  const [cronSchedule, setCronSchedule] = useState<string | null>(null);
  const [videoCount, setVideoCount] = useState<string | null>(null);
  const [runOnce, setRunOnce] = useState<boolean | null>(null);
  const [noUpload, setNoUpload] = useState<boolean | null>(null);
  const [notifyOnSuccess, setNotifyOnSuccess] = useState<boolean | null>(null);

  if (isPending) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError || !settings) {
    return (
      <p className="text-sm text-destructive">Couldn&apos;t load settings.</p>
    );
  }

  const handleSave = () => {
    const payload: SettingsUpdateRequest = {};

    for (const { field } of API_KEY_FIELDS) {
      const value = apiKeyInputs[field]?.trim();
      if (value) payload[field] = value;
    }
    if (appriseUrl.trim()) payload.apprise_url = appriseUrl.trim();
    if (geminiTextModel !== null) payload.gemini_text_model = geminiTextModel;
    if (openaiModel !== null) payload.openai_model = openaiModel;
    if (cronSchedule !== null) payload.cron_schedule = cronSchedule;
    if (videoCount !== null && videoCount.trim() !== "") {
      const n = Number(videoCount);
      if (Number.isFinite(n)) payload.video_count = n;
    }
    if (runOnce !== null) payload.run_once = runOnce;
    if (noUpload !== null) payload.no_upload = noUpload;
    if (notifyOnSuccess !== null) payload.notify_on_success = notifyOnSuccess;

    if (Object.keys(payload).length === 0) {
      toast("Nothing to save.");
      return;
    }

    updateSettings.mutate(payload, {
      onSuccess: (res) => {
        toast(
          res.restart_required
            ? "Saved - restart the API/cron process for changes to take effect."
            : "Saved.",
        );
        setApiKeyInputs({});
        setAppriseUrl("");
        setGeminiTextModel(null);
        setOpenaiModel(null);
        setCronSchedule(null);
        setVideoCount(null);
        setRunOnce(null);
        setNoUpload(null);
        setNotifyOnSuccess(null);
      },
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Save failed"),
    });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">
          API keys, provider models, and automation. Keys are write-only -
          existing values are never shown, only whether one is set.
        </p>
      </div>

      <Alert>
        <AlertTriangle className="size-4" />
        <AlertDescription>
          Changes are written to <code>.env</code> but only take effect after
          the API/cron process restarts.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="size-4" />
            API keys
          </CardTitle>
          <CardDescription>
            Leave a field blank to keep the current key.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {API_KEY_FIELDS.map(({ key, field, label, required }) => {
            const configured = settings.api_keys[key];
            const preview = settings.api_key_previews[key];
            return (
              <div key={field} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor={field}>{label}</Label>
                  <Badge variant={configured ? "secondary" : "outline"}>
                    {configured ? (preview ?? "Configured") : required ? "Required - not set" : "Not set"}
                  </Badge>
                </div>
                <Input
                  id={field}
                  type="password"
                  placeholder={configured ? "••••••••" : "Not set"}
                  autoComplete="off"
                  value={apiKeyInputs[field] ?? ""}
                  onChange={(e) =>
                    setApiKeyInputs((prev) => ({ ...prev, [field]: e.target.value }))
                  }
                />
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Models</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="gemini-text-model">Gemini text model</Label>
            <Input
              id="gemini-text-model"
              value={geminiTextModel ?? settings.gemini_text_model}
              onChange={(e) => setGeminiTextModel(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="openai-model">OpenAI model (fallback)</Label>
            <Input
              id="openai-model"
              value={openaiModel ?? settings.openai_model}
              onChange={(e) => setOpenaiModel(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Gemini TTS model</Label>
            <p className="text-sm text-muted-foreground">
              {settings.gemini_tts_model}{" "}
              <span className="text-xs">
                (set via <code>GEMINI_TTS_MODEL</code> in .env - not editable here)
              </span>
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="apprise-url">Apprise notification URL</Label>
              <Badge variant={settings.apprise_url_set ? "secondary" : "outline"}>
                {settings.apprise_url_set ? "Configured" : "Not set"}
              </Badge>
            </div>
            <Input
              id="apprise-url"
              type="password"
              placeholder={settings.apprise_url_set ? "••••••••" : "Not set"}
              autoComplete="off"
              value={appriseUrl}
              onChange={(e) => setAppriseUrl(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Notify on success</Label>
            <BoolSelect
              value={notifyOnSuccess ?? settings.notify_on_success}
              onChange={setNotifyOnSuccess}
              trueLabel="On"
              falseLabel="Off"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Automation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="cron-schedule">Cron schedule</Label>
            <Input
              id="cron-schedule"
              value={cronSchedule ?? settings.cron_schedule}
              onChange={(e) => setCronSchedule(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="video-count">Videos per run</Label>
            <Input
              id="video-count"
              type="number"
              min={1}
              value={videoCount ?? String(settings.video_count)}
              onChange={(e) => setVideoCount(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Run mode</Label>
            <BoolSelect
              value={runOnce ?? settings.run_once}
              onChange={setRunOnce}
              trueLabel="Run once and exit"
              falseLabel="Scheduled (cron)"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Uploads</Label>
            <BoolSelect
              value={noUpload ?? settings.no_upload}
              onChange={setNoUpload}
              trueLabel="Disabled (draft only)"
              falseLabel="Enabled (auto-publish)"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={updateSettings.isPending}>
          {updateSettings.isPending ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Save />
          )}
          Save changes
        </Button>
      </div>
    </div>
  );
}
