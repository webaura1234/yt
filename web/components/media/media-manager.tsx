"use client";

import { Music2, Sparkles, Trash2, Video, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { useDedupeMedia, useDeleteMedia, useMediaList } from "@/lib/hooks/use-media";
import { formatBytes } from "@/lib/utils";
import type { MediaItem } from "@/lib/api/types";

function MediaRow({
  item,
  onDelete,
}: {
  item: MediaItem;
  onDelete: (item: MediaItem) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
      <div className="min-w-0 space-y-1">
        <p className="truncate text-sm font-medium">{item.filename}</p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{formatBytes(item.size_bytes)}</span>
          <span>·</span>
          {item.attribution_required && item.credit ? (
            <span className="truncate" title={item.credit}>
              {item.credit}
            </span>
          ) : (
            <span>No attribution required</span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button variant="ghost" size="sm" asChild>
          <a href={api.media.assetUrl(item.url)} target="_blank" rel="noreferrer">
            Preview
          </a>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-destructive hover:text-destructive"
          onClick={() => onDelete(item)}
          aria-label={`Delete ${item.filename}`}
        >
          <Trash2 />
        </Button>
      </div>
    </div>
  );
}

function MediaSection({
  title,
  icon: Icon,
  items,
  isLoading,
  onDelete,
}: {
  title: string;
  icon: LucideIcon;
  items: MediaItem[] | undefined;
  isLoading: boolean;
  onDelete: (item: MediaItem) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-4" />
          {title}
          {items && <Badge variant="secondary">{items.length}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading &&
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        {!isLoading && items && items.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Nothing cached yet.
          </p>
        )}
        {items?.map((item) => (
          <MediaRow key={item.filename} item={item} onDelete={onDelete} />
        ))}
      </CardContent>
    </Card>
  );
}

export function MediaManager() {
  const { data, isPending, isError } = useMediaList();
  const dedupe = useDedupeMedia();
  const deleteMedia = useDeleteMedia();
  const [pendingDelete, setPendingDelete] = useState<MediaItem | null>(null);

  const handleDedupe = () => {
    dedupe.mutate(undefined, {
      onSuccess: (res) => {
        const total = res.music_removed + res.secondary_video_removed;
        toast(
          total > 0
            ? `Removed ${total} duplicate file${total === 1 ? "" : "s"}.`
            : "No duplicates found.",
        );
      },
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Dedupe failed"),
    });
  };

  const confirmDelete = () => {
    if (!pendingDelete) return;
    const target = pendingDelete;
    deleteMedia.mutate(
      { category: target.category, filename: target.filename },
      {
        onSuccess: () => toast(`Deleted ${target.filename}`),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Delete failed"),
        onSettled: () => setPendingDelete(null),
      },
    );
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Media manager</h2>
          <p className="text-sm text-muted-foreground">
            Cached music and stock footage, with license attribution.
          </p>
        </div>
        <Button variant="outline" onClick={handleDedupe} disabled={dedupe.isPending}>
          <Sparkles /> {dedupe.isPending ? "Deduping..." : "Remove duplicates"}
        </Button>
      </div>

      {isError && (
        <p className="text-sm text-destructive">Couldn&apos;t load cached media.</p>
      )}

      <MediaSection
        title="Background music"
        icon={Music2}
        items={data?.music}
        isLoading={isPending}
        onDelete={setPendingDelete}
      />
      <MediaSection
        title="Stock footage"
        icon={Video}
        items={data?.secondary_video}
        isLoading={isPending}
        onDelete={setPendingDelete}
      />

      <AlertDialog
        open={!!pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this file?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete &&
                `${pendingDelete.filename} will be permanently removed from the cache. This can't be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteMedia.isPending}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
