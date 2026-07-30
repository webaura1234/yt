"use client";

import { Keyboard } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { navItems } from "@/lib/nav-items";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpenHelp?: () => void;
}

export function CommandPalette({ open, onOpenChange, onOpenHelp }: CommandPaletteProps) {
  const router = useRouter();

  const go = (href: string) => {
    onOpenChange(false);
    router.push(href);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command Palette"
      description="Jump to a page or run a quick action"
    >
      <CommandInput placeholder="Search pages and actions..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Quick actions">
          <CommandItem onSelect={() => go("/generate")}>
            New video generation
          </CommandItem>
          {onOpenHelp && (
            <CommandItem
              onSelect={() => {
                onOpenChange(false);
                onOpenHelp();
              }}
            >
              <Keyboard />
              Keyboard shortcuts
            </CommandItem>
          )}
        </CommandGroup>
        <CommandGroup heading="Pages">
          {navItems.map((item) => (
            <CommandItem key={item.href} onSelect={() => go(item.href)}>
              <item.icon />
              {item.title}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
