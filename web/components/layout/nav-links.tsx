"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { navItems } from "@/lib/nav-items";

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-1">
      {navItems.map((item) => {
        const isActive =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              "hover:bg-accent hover:text-accent-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              isActive ? "text-foreground" : "text-muted-foreground",
            )}
          >
            {isActive && (
              <motion.span
                layoutId="active-nav-pill"
                className="absolute inset-0 rounded-lg bg-accent"
                transition={{ type: "spring", stiffness: 400, damping: 35 }}
              />
            )}
            <item.icon className="relative size-4 shrink-0" />
            <span className="relative">{item.title}</span>
          </Link>
        );
      })}
    </nav>
  );
}
