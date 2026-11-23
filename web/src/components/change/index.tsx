import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BellRing,
  CircleCheck,
  CircleX,
  FilePen,
  FilePlus2,
  FileText,
  Gavel,
  Minus,
  ShieldCheck,
  ShieldOff,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { inr, num } from "../../lib/format";
import { ago } from "../../lib/time";
import type { ChangeEvent, ChangeKind } from "../../lib/types";
import { Skeleton } from "../ui";

/* ------------------------------------------------------------------ formatting */

export type Unit = "points" | "pts" | "pct" | "share" | "inr" | "kwh" | "days" | "count" | "hours" | "";

/** A value in its unit: ₹ in lakh/crore, shares as %, hours as min / h / days. */
export function fmtValue(v: number | null | undefined, unit: Unit | string = ""): string {
  if (v == null || Number.isNaN(v)) return "–";
  switch (unit) {
    case "inr":
      return inr(v);
    case "share":
    case "pct":
      return `${(v * 100).toFixed(0)}%`;
    case "kwh":
      return `${num(v)} kWh`;
    case "days":
      return `${Math.round(v)} ${Math.round(v) === 1 ? "day" : "days"}`;
    case "hours":
      return v < 1 ? `${Math.max(1, Math.round(v * 60))} min` : v < 48 ? `${v.toFixed(1)} h` : `${(v / 24).toFixed(1)} days`;
    default:
      return num(v);
  }
}

/** The size of a change in its unit: relative % for money and kWh, percentage points for shares, else plain. */
function fmtDelta(before: number | null | undefined, after: number | null | undefined, unit: string, delta?: number | null): string {
  const d = delta ?? (before != null && after != null ? after - before : null);
  if (d == null) return "";
  const abs = Math.abs(d);
  if ((unit === "inr" || unit === "kwh") && before) return `${Math.round((abs / Math.abs(before)) * 100)}%`;
  if (unit === "share" || unit === "pct" || unit === "pts") return `${Math.round(abs * 100)} pts`;
  if (unit === "hours") return fmtValue(abs, "hours");
  if (unit === "days") return `${Math.round(abs)} ${Math.round(abs) === 1 ? "day" : "days"}`;
  return num(abs);
}

/* ------------------------------------------------------------------ Delta */

/**
 * An arrow chip for a change. Direction-aware: forest when the change is good, brick when it is bad, so a falling
 * risk reads as good. The arrow always shows which way the number moved; colour is never the only signal.
 */
export function Delta({
  value,
  before,
  after,
  unit = "",
  goodWhenUp = true,
  suffix,
  className,
  size = "md",
}: {
  /** The change itself (after − before). Give this, or `before` and `after`. */
  value?: number | null;
  before?: number | null;
  after?: number | null;
  unit?: Unit | string;
  goodWhenUp?: boolean;
  /** Plain words after the number, e.g. "since yesterday". */
  suffix?: ReactNode;
  className?: string;
  size?: "sm" | "md";
}) {
  const d = value ?? (before != null && after != null ? after - before : null);
  if (d == null) return null;
  const flat = Math.abs(d) < 1e-9;
  const up = d > 0;
  const good = flat ? null : up === goodWhenUp;
  const Icon = flat ? Minus : up ? ArrowUp : ArrowDown;
  const text = flat ? "no change" : fmtDelta(before, after, unit, d);
  const word = flat ? "unchanged" : `${up ? "up" : "down"} ${text}, ${good ? "better" : "worse"}`;
  return (
    <span
      className={cn(
        "tabular inline-flex items-center gap-1 rounded-md font-semibold whitespace-nowrap",
        size === "sm" ? "px-1.5 py-px text-xs" : "px-2 py-0.5 text-13",
        good == null ? "bg-panel-2 text-fg-muted" : good ? "bg-success-tint text-success" : "bg-danger-tint text-danger",
        className,
      )}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} strokeWidth={2.5} aria-hidden />
      <span aria-hidden>{text}</span>
      {suffix && (
        <span aria-hidden className="font-medium">
          {suffix}
        </span>
      )}
      <span className="sr-only">
        {word}
        {typeof suffix === "string" ? ` ${suffix}` : ""}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ BeforeAfter */

/** The old value struck through and subtle → arrow → the new value bold → a `<Delta>`. */
export function BeforeAfter({
  before,
  after,
  unit = "",
  goodWhenUp = true,
  size = "md",
  className,
}: {
  before: number | null | undefined;
  after: number | null | undefined;
  unit?: Unit | string;
  goodWhenUp?: boolean;
  size?: "md" | "lg";
  className?: string;
}) {
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-x-2 gap-y-1", className)}>
      {before != null && (
        <>
          <s className={cn("tabular text-fg-muted", size === "lg" ? "text-base" : "text-13")}>
            <span className="sr-only">was </span>
            {fmtValue(before, unit)}
          </s>
          <ArrowRight className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden />
        </>
      )}
      <span className={cn("tabular font-bold text-fg", size === "lg" ? "text-2xl tracking-[-0.5px]" : "text-sm")}>
        {before != null && <span className="sr-only">now </span>}
        {fmtValue(after, unit)}
      </span>
      <Delta before={before} after={after} unit={unit} goodWhenUp={goodWhenUp} size="sm" />
    </span>
  );
}

/* ------------------------------------------------------------------ ChangedMarker */

/** "New" or "Updated" in pink: the item changed after the user last looked. */
export function ChangeBadge({ kind, className }: { kind: ChangeKind | undefined; className?: string }) {
  if (!kind) return null;
  return (
    <span className={cn("inline-flex items-center rounded-md bg-brand-tint px-1.5 py-px text-[11px] font-bold tracking-[0.5px] text-brand uppercase", className)}>
      {kind === "new" ? "New" : "Updated"}
      <span className="sr-only">: changed since you last looked</span>
    </span>
  );
}

/** A 3px pink bar on the left edge of a row or card. Put it inside a `relative` container. */
export function ChangedBar({ show, className }: { show: boolean | undefined; className?: string }) {
  if (!show) return null;
  return <span aria-hidden className={cn("absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-brand", className)} />;
}

/** Legend under every list that shows change markers. */
export function ChangedHint({ children, action }: { children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-13 text-fg-muted">
      <p className="inline-flex items-center gap-2">
        <span className="h-3.5 w-[3px] rounded-full bg-brand" aria-hidden />
        {children ?? "Pink bar = changed since you last looked"}
      </p>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ WhatChanged */

const EVENT_LOOK: Record<string, { icon: LucideIcon; tone: string }> = {
  opened: { icon: FilePlus2, tone: "bg-panel-2 text-fg-muted" },
  scored: { icon: TrendingUp, tone: "bg-success-tint text-success" },
  score_changed: { icon: TrendingUp, tone: "bg-success-tint text-success" },
  memo_ready: { icon: FileText, tone: "bg-purple-tint text-purple" },
  memo_updated: { icon: FilePen, tone: "bg-purple-tint text-purple" },
  decided: { icon: Gavel, tone: "bg-success-tint text-success" },
  state_changed: { icon: ArrowRight, tone: "bg-panel-2 text-fg-muted" },
  alert_raised: { icon: BellRing, tone: "bg-danger-tint text-danger" },
  alert_actioned: { icon: CircleCheck, tone: "bg-success-tint text-success" },
  consent_granted: { icon: ShieldCheck, tone: "bg-info-tint text-info" },
  consent_revoked: { icon: ShieldOff, tone: "bg-danger-tint text-danger" },
  consent_expired: { icon: ShieldOff, tone: "bg-warning-tint text-warning" },
};

function look(e: ChangeEvent): { icon: LucideIcon; tone: string } {
  const base = EVENT_LOOK[e.event_type] ?? { icon: ArrowRight, tone: "bg-panel-2 text-fg-muted" };
  const b = e.before?.score as number | null | undefined;
  const a = e.after?.score as number | null | undefined;
  if (e.event_type === "score_changed" && b != null && a != null && a < b) return { icon: TrendingDown, tone: "bg-danger-tint text-danger" };
  if (e.event_type === "decided" && e.after?.decision === "REJECTED") return { icon: CircleX, tone: "bg-danger-tint text-danger" };
  return base;
}

/** Splits "Title. Detail" summaries into a title line and a one-line detail. */
function split(summary: string): [string, string | null] {
  const i = summary.search(/[.:] /);
  return i > 0 ? [summary.slice(0, i), summary.slice(i + 2)] : [summary, null];
}

function when(iso: string): string {
  const d = new Date(iso);
  const days = (Date.now() - d.getTime()) / 86_400_000;
  if (days < 1) return ago(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

/** Timeline of changes, newest first. Each entry: an icon tile in its meaning's colour, a title, a detail line, a time. */
export function WhatChanged({
  items,
  loading,
  empty = "Nothing has changed yet.",
  limit,
  className,
}: {
  items: ChangeEvent[] | undefined;
  loading?: boolean;
  empty?: string;
  limit?: number;
  className?: string;
}) {
  if (loading)
    return (
      <div role="status" aria-label="Loading changes" className="space-y-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="h-9 w-9 rounded-control" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  if (!items?.length) return <p className="text-13 text-fg-muted">{empty}</p>;
  const shown = limit ? items.slice(0, limit) : items;
  return (
    <ol className={cn("space-y-5", className)}>
      {shown.map((e) => {
        const { icon: Icon, tone } = look(e);
        const [title, fromSummary] = split(e.summary);
        const detail = e.detail ?? fromSummary;
        return (
          <li key={e.id} className="flex gap-3">
            <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-control", tone)} aria-hidden>
              <Icon className="h-[18px] w-[18px]" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-fg">
                  {title}
                  {e.new && <ChangeBadge kind="new" className="ml-2 align-middle" />}
                </p>
                <time dateTime={e.created_at} className="tabular shrink-0 pt-0.5 text-xs text-fg-muted" title={new Date(e.created_at).toLocaleString("en-IN")}>
                  {when(e.created_at)}
                </time>
              </div>
              {(detail || e.actor) && (
                <p className="mt-0.5 text-13 text-fg-muted">
                  {detail}
                  {detail && e.actor ? " · " : ""}
                  {e.actor && <span>by {e.actor}</span>}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
