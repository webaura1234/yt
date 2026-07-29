import Link from "next/link";
import { Compass } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="rounded-full bg-muted p-4">
        <Compass className="size-8 text-muted-foreground" aria-hidden="true" />
      </div>
      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold">Page not found</h2>
        <p className="text-sm text-muted-foreground">
          That page doesn&apos;t exist. Use the sidebar or press ⌘K to find
          what you&apos;re looking for.
        </p>
      </div>
      <Button asChild>
        <Link href="/">Back to Home</Link>
      </Button>
    </div>
  );
}
