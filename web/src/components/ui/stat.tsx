import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Skeleton } from "./states";

/** KPI tile. `delta` shows a trend arrow + text; `goodWhen` decides whether up is good (colour) — the arrow always shows direction. */
export function Stat({
  label,
  value,
  sub,
  delta,
  deltaLabel,
  goodWhen = "up",
  loading,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  delta?: number | null;
  deltaLabel?: string;
  goodWhen?: "up" | "down";
  loading?: boolean;
  className?: string;
}) {
  const dir = delta == null || delta === 0 ? "flat" : delta > 0 ? "up" : "down";
  const good = dir === "flat" ? null : dir === goodWhen;
  const Icon = dir === "up" ? TrendingUp : dir === "down" ? TrendingDown : Minus;
  return (
    <div className={cn("rounded-card border border-edge bg-panel p-4 shadow-card", className)}>
      <p className="text-xs font-medium text-fg-muted">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-24" />
      ) : (
        <p className="tabular mt-1 text-2xl font-semibold text-fg" data-numeric>
          {value}
        </p>
      )}
      {delta != null && !loading && (
        <p className={cn("mt-1 inline-flex items-center gap-1 text-xs font-medium", good == null ? "text-fg-muted" : good ? "text-success" : "text-danger")}>
          <Icon className="h-3.5 w-3.5" aria-hidden />
          <span className="tabular">{deltaLabel ?? `${delta > 0 ? "+" : ""}${delta}`}</span>
        </p>
      )}
      {sub && !loading && <div className="mt-1 text-xs text-fg-muted">{sub}</div>}
    </div>
  );
}
