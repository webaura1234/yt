import { Check, X } from "lucide-react";

import type { ApiKeyStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const LABELS: Record<keyof ApiKeyStatus, string> = {
  gemini: "Gemini (script + TTS)",
  openai: "OpenAI (fallback)",
  pexels: "Pexels (stock footage)",
  assembly_ai: "AssemblyAI (subtitles)",
  news_api: "NewsAPI (unused today)",
};

export function ApiKeyChecklist({ status }: { status: ApiKeyStatus }) {
  return (
    <ul className="space-y-2">
      {(Object.keys(LABELS) as (keyof ApiKeyStatus)[]).map((key) => {
        const configured = status[key];
        return (
          <li key={key} className="flex items-center gap-2 text-sm">
            {configured ? (
              <Check className="size-4 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <X className="size-4 text-muted-foreground" />
            )}
            <span
              className={cn(!configured && "text-muted-foreground")}
            >
              {LABELS[key]}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
