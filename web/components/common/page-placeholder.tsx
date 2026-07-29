import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function PagePlaceholder({
  icon: Icon,
  title,
  description,
  phase,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  phase: string;
}) {
  return (
    <Card className="mx-auto max-w-xl">
      <CardContent className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="rounded-full bg-muted p-4">
          <Icon className="size-8 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="space-y-1.5">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <Badge variant="secondary">Coming in {phase}</Badge>
      </CardContent>
    </Card>
  );
}
