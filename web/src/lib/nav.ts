import { ChartPie, LayoutList, ShieldCheck, Smartphone, type LucideIcon } from "lucide-react";
import type { Role } from "./auth";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: Role[];
  /** Two-key shortcut shown in the shortcut sheet, e.g. "g c". */
  keys?: string;
}

export const NAV: NavItem[] = [
  { to: "/console", label: "Credit console", icon: LayoutList, roles: ["rm", "credit_officer"], keys: "g c" },
  { to: "/cockpit", label: "Risk cockpit", icon: ChartPie, roles: ["rm", "credit_officer", "risk"], keys: "g p" },
  { to: "/governance", label: "Governance", icon: ShieldCheck, roles: ["risk"], keys: "g g" },
  { to: "/msme", label: "My business", icon: Smartphone, roles: ["msme"] },
];

export const navFor = (role: Role) => NAV.filter((n) => n.roles.includes(role));

/** Breadcrumb trail for a pathname. */
export function crumbs(pathname: string): { label: string; to?: string }[] {
  const parts = pathname.split("/").filter(Boolean);
  const root = NAV.find((n) => n.to === `/${parts[0]}`);
  if (!root) return [];
  const out: { label: string; to?: string }[] = [{ label: root.label, to: parts.length > 1 ? root.to : undefined }];
  if (parts[0] === "console" && parts[1]) out.push({ label: `Application #${parts[1]}` });
  return out;
}
