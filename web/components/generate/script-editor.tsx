"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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
import { Textarea } from "@/components/ui/textarea";
import { useVoices } from "@/lib/hooks/use-topics";
import type { JobResponse } from "@/lib/api/types";

export function ScriptEditor({
  job,
  onContinue,
  isSaving,
  isContinuing,
}: {
  job: JobResponse;
  onContinue: (fields: {
    title: string;
    script: string;
    description: string;
    voice: string;
  }) => void;
  isSaving: boolean;
  isContinuing: boolean;
}) {
  const [title, setTitle] = useState(job.title ?? "");
  const [script, setScript] = useState(job.script ?? "");
  const [description, setDescription] = useState(job.description ?? "");
  const [voice, setVoice] = useState(job.voice ?? "");

  const { data: voices, isPending: voicesPending } = useVoices();

  const busy = isSaving || isContinuing;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review your script</CardTitle>
        <CardDescription>
          Edit anything before rendering — this is the last step before media
          and voice generation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="gen-title">Title</Label>
          <Input
            id="gen-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="gen-script">Script</Label>
          <Textarea
            id="gen-script"
            rows={6}
            value={script}
            onChange={(e) => setScript(e.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="gen-description">Description</Label>
          <Textarea
            id="gen-description"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {job.search_terms && job.search_terms.length > 0 && (
          <div className="space-y-1.5">
            <Label>Footage search terms</Label>
            <div className="flex flex-wrap gap-1.5">
              {job.search_terms.map((term) => (
                <Badge key={term} variant="secondary">
                  {term}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-1.5">
          <Label>Voice</Label>
          {voicesPending ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <Select value={voice} onValueChange={setVoice}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Default voice" />
              </SelectTrigger>
              <SelectContent>
                {voices?.map((v) => (
                  <SelectItem key={v.name} value={v.name}>
                    {v.name}
                    {!v.verified && " (unverified)"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          disabled={busy || !title.trim() || !script.trim()}
          onClick={() => onContinue({ title, script, description, voice })}
        >
          {busy ? <Loader2 className="animate-spin" /> : <ArrowRight />}
          Continue to render
        </Button>
      </CardFooter>
    </Card>
  );
}
