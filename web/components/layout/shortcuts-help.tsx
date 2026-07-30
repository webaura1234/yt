"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { GO_TO_SHORTCUTS } from "@/lib/hooks/use-global-shortcuts";

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs font-medium">
      {children}
    </kbd>
  );
}

export function ShortcutsHelp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Works anywhere except while typing in a field.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Open command palette</span>
            <div className="flex items-center gap-1">
              <Kbd>&#8984;</Kbd>
              <Kbd>K</Kbd>
            </div>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Show this help</span>
            <Kbd>?</Kbd>
          </div>
          <div className="border-t pt-3">
            <p className="mb-2 text-sm font-medium">Go to page</p>
            <div className="space-y-2">
              {GO_TO_SHORTCUTS.map(({ key, label }) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{label}</span>
                  <div className="flex items-center gap-1">
                    <Kbd>G</Kbd>
                    <Kbd>{key.toUpperCase()}</Kbd>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
