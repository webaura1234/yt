"use client";

import { Menu, Search } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { NavLinks } from "@/components/layout/nav-links";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { navItems } from "@/lib/nav-items";

export function Topbar({
  onOpenCommandPalette,
}: {
  onOpenCommandPalette: () => void;
}) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const current = navItems.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4">
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation menu"
          >
            <Menu className="size-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader className="h-14 justify-center border-b px-4">
            <SheetTitle className="text-left">Shorts Studio</SheetTitle>
          </SheetHeader>
          <div className="p-3">
            <NavLinks onNavigate={() => setMobileOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <h1 className="font-semibold">{current?.title ?? "Dashboard"}</h1>

      <div className="ml-auto flex items-center gap-2">
        <Button
          variant="outline"
          className="hidden items-center gap-2 text-muted-foreground sm:flex"
          onClick={onOpenCommandPalette}
        >
          <Search className="size-4" />
          <span className="text-sm">Search...</span>
          <kbd className="ml-4 rounded border bg-muted px-1.5 py-0.5 text-xs">
            &#8984;K
          </kbd>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="sm:hidden"
          aria-label="Search"
          onClick={onOpenCommandPalette}
        >
          <Search className="size-4" />
        </Button>
        <ThemeToggle />
      </div>
    </header>
  );
}
