import { Sparkles } from "lucide-react";
import Link from "next/link";

import { ScrollArea } from "@/components/ui/scroll-area";
import { NavLinks } from "@/components/layout/nav-links";

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r bg-sidebar md:flex md:flex-col">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
        >
          <Sparkles className="size-5 text-primary" aria-hidden="true" />
          <span>Shorts Studio</span>
        </Link>
      </div>
      <ScrollArea className="flex-1 px-3 py-4">
        <NavLinks />
      </ScrollArea>
    </aside>
  );
}
