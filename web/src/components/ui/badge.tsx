import { CircleAlert, CircleCheck, Contrast, Info, Sparkles, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { BAND_LABEL, type Band, type Severity } from "../../lib/format";

export type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "info" | "brand";

const TONE: Record<Tone, string> = {
  neutral: "bg-panel-2 text-fg-muted",
  primary: "bg-primary-tint text-primary",
  success: "bg-success-tint text-success",
  warning: "bg-warning-tint text-warning",
  danger: "bg-danger-tint text-danger",
  info: "bg-info-tint text-info",
  brand: "bg-brand-tint text-fg",
};

export function Badge({ tone = "neutral", icon, children, className }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", TONE[tone], className)}>
      {icon}
      {children}
    </span>
  );
}

const ICON = "h-3.5 w-3.5 shrink-0";

const BAND: Record<Band, { tone: Tone; icon: ReactNode }> = {
  APPROVE: { tone: "success", icon: <CircleCheck className={ICON} aria-hidden /> },
  WATCH: { tone: "warning", icon: <Contrast className={ICON} aria-hidden /> },
  HIGH_RISK: { tone: "danger", icon: <TriangleAlert className={ICON} aria-hidden /> },
};

/** Risk band: always icon + label + colour, never colour alone. */
export function BandPill({ band, className }: { band?: string | null; className?: string }) {
  if (!band || !(band in BAND)) return <span className="text-fg-muted">–</span>;
  const b = BAND[band as Band];
  return (
    <Badge tone={b.tone} icon={b.icon} className={className}>
      {BAND_LABEL[band as Band]}
    </Badge>
  );
}

const SEVERITY: Record<Severity, { tone: Tone; icon: ReactNode; label: string }> = {
  high: { tone: "danger", icon: <TriangleAlert className={ICON} aria-hidden />, label: "High" },
  medium: { tone: "warning", icon: <CircleAlert className={ICON} aria-hidden />, label: "Medium" },
  low: { tone: "info", icon: <Info className={ICON} aria-hidden />, label: "Low" },
};

export function SeverityPill({ severity, className }: { severity?: string | null; className?: string }) {
  if (!severity || !(severity in SEVERITY)) return null;
  const s = SEVERITY[severity as Severity];
  return (
    <Badge tone={s.tone} icon={s.icon} className={className}>
      {s.label}
    </Badge>
  );
}

export function AiLabel({ className }: { className?: string }) {
  return (
    <Badge tone="primary" icon={<Sparkles className={ICON} aria-hidden />} className={className}>
      AI-generated recommendation · final decision by credit officer
    </Badge>
  );
}
