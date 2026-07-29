import {
  BarChart3,
  FolderOpen,
  LayoutDashboard,
  Settings,
  Sparkles,
  Terminal,
  TrendingUp,
  Upload,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

export const navItems: NavItem[] = [
  {
    title: "Home",
    href: "/",
    icon: LayoutDashboard,
    description: "System health, stats, and activity",
  },
  {
    title: "Generate",
    href: "/generate",
    icon: Sparkles,
    description: "Create a new video from a topic",
  },
  {
    title: "Trends",
    href: "/trends",
    icon: TrendingUp,
    description: "Topic scoring and suggestions",
  },
  {
    title: "Media",
    href: "/media",
    icon: FolderOpen,
    description: "Cached music and stock footage",
  },
  {
    title: "Uploads",
    href: "/uploads",
    icon: Upload,
    description: "Publish history and YouTube status",
  },
  {
    title: "Analytics",
    href: "/analytics",
    icon: BarChart3,
    description: "Generation history and performance",
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
    description: "API keys, providers, rendering options",
  },
  {
    title: "Developer",
    href: "/developer",
    icon: Terminal,
    description: "Logs, diagnostics, manual pipeline runs",
  },
];
