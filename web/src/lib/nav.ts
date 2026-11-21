import { Activity, Bell, ChartPie, Inbox, ShieldCheck, Smartphone, type LucideIcon } from "lucide-react";
import type { Role } from "./auth";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: Role[];
  /** Two-key shortcut shown in the shortcut sheet, e.g. "g c". */
  keys?: string;
  /** Which actionable count, if any, the sidebar shows as a pink badge. */
  count?: "applications" | "alerts";
}

const STAFF: Role[] = ["rm", "credit_officer", "risk"];

export const NAV: NavItem[] = [
  { to: "/console", label: "Applications", icon: Inbox, roles: ["rm", "credit_officer"], keys: "g c", count: "applications" },
  { to: "/alerts", label: "Alerts", icon: Bell, roles: STAFF, keys: "g a", count: "alerts" },
  { to: "/portfolio", label: "Portfolio", icon: ChartPie, roles: STAFF, keys: "g p" },
  { to: "/governance", label: "Governance", icon: ShieldCheck, roles: ["risk"], keys: "g g" },
  { to: "/system", label: "System", icon: Activity, roles: STAFF, keys: "g s" },
  { to: "/msme", label: "My business", icon: Smartphone, roles: ["msme"] },
];

export const navFor = (role: Role) => NAV.filter((n) => n.roles.includes(role));
