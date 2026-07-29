import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  icon: Icon,
  label,
  value,
  subLabel,
  className,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  subLabel?: string;
  className?: string;
}) {
  return (
    <Card className={cn(className)}>
      <CardContent className="flex items-center gap-4">
        <div className="rounded-lg bg-muted p-2.5">
          <Icon className="size-5 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="truncate text-2xl font-semibold">{value}</p>
          {subLabel && (
            <p className="text-xs text-muted-foreground">{subLabel}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
