"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

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
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useTopics } from "@/lib/hooks/use-topics";
import { cn } from "@/lib/utils";

export function TopicPicker({
  onGenerate,
  isGenerating,
}: {
  onGenerate: (topic: string) => void;
  isGenerating: boolean;
}) {
  const { data: topics, isPending, isError } = useTopics();
  const [selected, setSelected] = useState<string | null>(null);
  const [customTopic, setCustomTopic] = useState("");

  const effectiveTopic = customTopic.trim() || selected;

  const handleSelect = (topic: string) => {
    setSelected(topic);
    setCustomTopic("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Choose a topic</CardTitle>
        <CardDescription>
          Pick an AI-scored suggestion, or write your own.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPending && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {isError && (
          <p className="text-sm text-destructive">
            Couldn&apos;t load topic suggestions - you can still write your own below.
          </p>
        )}

        {topics && topics.length > 0 && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {topics.map((t) => (
              <button
                key={t.topic}
                type="button"
                onClick={() => handleSelect(t.topic)}
                className={cn(
                  "rounded-lg border p-3 text-left text-sm transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected === t.topic && !customTopic
                    ? "border-primary bg-accent"
                    : "hover:bg-accent/50",
                )}
              >
                <p className="font-medium">{t.topic}</p>
                {t.times_used > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Used {t.times_used}x before
                  </p>
                )}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3">
          <Separator className="flex-1" />
          <span className="text-xs text-muted-foreground">or</span>
          <Separator className="flex-1" />
        </div>

        <Input
          placeholder="Write your own topic..."
          value={customTopic}
          onChange={(e) => {
            setCustomTopic(e.target.value);
            setSelected(null);
          }}
        />
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          disabled={!effectiveTopic || isGenerating}
          onClick={() => effectiveTopic && onGenerate(effectiveTopic)}
        >
          {isGenerating ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Sparkles />
          )}
          Generate
        </Button>
      </CardFooter>
    </Card>
  );
}
