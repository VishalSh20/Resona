import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bot,
  LayoutDashboard,
} from "lucide-react";

export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  end?: boolean;
}

export const primaryNav: NavItem[] = [
  { label: "Overview", path: "/app", icon: LayoutDashboard, end: true },
  { label: "Agents", path: "/app/agents", icon: Bot },
  { label: "Simulations", path: "/app/simulations", icon: Activity },
];
