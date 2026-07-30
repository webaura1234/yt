"use client";

import { Loader2, Search, Sparkles, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCustomTopic, useTopics } from "@/lib/hooks/use-topics";
import { formatRelativeTime } from "@/lib/utils";
import type { TopicSuggestion } from "@/lib/api/types";

type SortKey = "score" | "times_used" | "alphabetical";

function sortTopics(topics: TopicSuggestion[], sortKey: SortKey): TopicSuggestion[] {
  const sorted = [...topics];
  switch (sortKey) {
    case "times_used":
      return sorted.sort((a, b) => b.times_used - a.times_used);
    case "alphabetical":
      return sorted.sort((a, b) => a.topic.localeCompare(b.topic));
    case "score":
    default:
      return sorted.sort((a, b) => b.score - a.score);
  }
}

function TopicRow({ topic }: { topic: TopicSuggestion }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
      <div className="min-w-0 space-y-1">
        <p className="truncate text-sm font-medium">{topic.topic}</p>
        <p className="text-xs text-muted-foreground">
          {topic.times_used > 0
            ? `Used ${topic.times_used}x · last ${formatRelativeTime(topic.last_used_at as string)}`
            : "Never used"}
        </p>
      </div>
      <Badge variant="secondary" className="shrink-0">
        score {topic.score.toFixed(3)}
      </Badge>
    </div>
  );
}

export function TrendExplorer() {
  const { data: topics, isPending, isError } = useTopics();
  const customTopic = useCustomTopic();

  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [checkInput, setCheckInput] = useState("");

  const filtered = useMemo(() => {
    if (!topics) return [];
    const q = query.trim().toLowerCase();
    const matching = q
      ? topics.filter((t) => t.topic.toLowerCase().includes(q))
      : topics;
    return sortTopics(matching, sortKey);
  }, [topics, query, sortKey]);

  const handleCheck = () => {
    const topic = checkInput.trim();
    if (!topic) return;
    customTopic.mutate(topic);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Trend discovery</h2>
        <p className="text-sm text-muted-foreground">
          Every topic scored by how recently/often it&apos;s been used - topics
          that haven&apos;t run yet score highest, so generation naturally
          rotates instead of repeating.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Score a custom topic</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input
            placeholder="Type a topic to see its score..."
            value={checkInput}
            onChange={(e) => setCheckInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCheck()}
          />
          <Button
            onClick={handleCheck}
            disabled={!checkInput.trim() || customTopic.isPending}
          >
            {customTopic.isPending ? (
              <Loader2 className="animate-spin" />
            ) : (
              <Sparkles />
            )}
            Check score
          </Button>
        </CardContent>
        {customTopic.data && (
          <CardContent className="pt-0">
            <TopicRow topic={customTopic.data} />
          </CardContent>
        )}
        {customTopic.isError && (
          <CardContent className="pt-0">
            <p className="text-sm text-destructive">Couldn&apos;t score that topic.</p>
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="size-4" />
            All topics
            {topics && <Badge variant="secondary">{topics.length}</Badge>}
          </CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Filter..."
                className="h-8 w-40 pl-8"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
              <SelectTrigger size="sm" className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="score">Sort: score</SelectItem>
                <SelectItem value="times_used">Sort: most used</SelectItem>
                <SelectItem value="alphabetical">Sort: A-Z</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {isPending &&
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}

          {isError && (
            <p className="text-sm text-destructive">Couldn&apos;t load topics.</p>
          )}

          {!isPending && filtered.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No topics match &quot;{query}&quot;.
            </p>
          )}

          {filtered.map((t) => (
            <TopicRow key={t.topic} topic={t} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
