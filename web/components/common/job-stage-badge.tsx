import {
  CheckCircle2,
  CircleDashed,
  Loader2,
  PauseCircle,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { JobStage } from "@/lib/api/types";

const STAGE_CONFIG: Record<
  JobStage,
  { label: string; icon: typeof Loader2; className: string; spin?: boolean }
> = {
  pending: {
    label: "Pending",
    icon: CircleDashed,
    className: "text-muted-foreground border-muted-foreground/30",
  },
  generating_script: {
    label: "Writing script",
    icon: Loader2,
    className: "text-blue-600 border-blue-500/30 dark:text-blue-400",
    spin: true,
  },
  script_ready: {
    label: "Script ready",
    icon: PauseCircle,
    className: "text-amber-600 border-amber-500/30 dark:text-amber-400",
  },
  fetching_media: {
    label: "Fetching media",
    icon: Loader2,
    className: "text-blue-600 border-blue-500/30 dark:text-blue-400",
    spin: true,
  },
  rendering: {
    label: "Rendering",
    icon: Loader2,
    className: "text-blue-600 border-blue-500/30 dark:text-blue-400",
    spin: true,
  },
  rendered: {
    label: "Rendered",
    icon: PauseCircle,
    className: "text-amber-600 border-amber-500/30 dark:text-amber-400",
  },
  publishing: {
    label: "Publishing",
    icon: Loader2,
    className: "text-blue-600 border-blue-500/30 dark:text-blue-400",
    spin: true,
  },
  done: {
    label: "Done",
    icon: CheckCircle2,
    className: "text-emerald-600 border-emerald-500/30 dark:text-emerald-400",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    className: "text-destructive border-destructive/30",
  },
  cancelled: {
    label: "Cancelled",
    icon: XCircle,
    className: "text-muted-foreground border-muted-foreground/30",
  },
};

export function JobStageBadge({ stage }: { stage: JobStage }) {
  const config = STAGE_CONFIG[stage];
  const Icon = config.icon;

  return (
    <Badge variant="outline" className={cn("gap-1.5", config.className)}>
      <Icon className={cn("size-3", config.spin && "animate-spin")} />
      {config.label}
    </Badge>
  );
}
