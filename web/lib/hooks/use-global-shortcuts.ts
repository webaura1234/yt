"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

// "g" is a leader key (like GitHub/Linear/Gmail) - press g, then one of these
// within the timeout, to jump straight to a page without touching the mouse.
export const GO_TO_SHORTCUTS: { key: string; label: string; href: string }[] = [
  { key: "h", label: "Home", href: "/" },
  { key: "n", label: "Generate (new video)", href: "/generate" },
  { key: "t", label: "Trends", href: "/trends" },
  { key: "m", label: "Media", href: "/media" },
  { key: "u", label: "Uploads", href: "/uploads" },
  { key: "a", label: "Analytics", href: "/analytics" },
  { key: "s", label: "Settings", href: "/settings" },
  { key: "d", label: "Developer", href: "/developer" },
];

const GO_TO_MAP: Record<string, string> = Object.fromEntries(
  GO_TO_SHORTCUTS.map(({ key, href }) => [key, href]),
);

const LEADER_TIMEOUT_MS = 1500;

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable
  );
}

export function useGlobalShortcuts({
  onOpenCommandPalette,
  onOpenHelp,
}: {
  onOpenCommandPalette: () => void;
  onOpenHelp: () => void;
}) {
  const router = useRouter();
  const leaderActive = useRef(false);
  const leaderTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function clearLeader() {
      leaderActive.current = false;
      if (leaderTimer.current) {
        clearTimeout(leaderTimer.current);
        leaderTimer.current = null;
      }
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenCommandPalette();
        return;
      }

      // Never hijack typing in a form field, or any OS/browser modifier combo.
      if (isEditableTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey) {
        return;
      }

      if (leaderActive.current) {
        const href = GO_TO_MAP[e.key];
        clearLeader();
        if (href) {
          e.preventDefault();
          router.push(href);
        }
        return;
      }

      if (e.key === "g") {
        leaderActive.current = true;
        leaderTimer.current = setTimeout(clearLeader, LEADER_TIMEOUT_MS);
        return;
      }

      if (e.key === "?") {
        e.preventDefault();
        onOpenHelp();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      clearLeader();
    };
  }, [router, onOpenCommandPalette, onOpenHelp]);
}
