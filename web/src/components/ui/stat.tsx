import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Skeleton } from "./states";

/** KPI tile: an uppercase label, a large value, and an optional delta chip or context line beside it. */
export function Stat({
  label,
  value,
  delta,
  sub,
  loading,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  /** A `<Delta>` chip (or any inline element) shown next to the value. */
  delta?: ReactNode;
  /** Context in plain words, shown beside or under the value. */
  sub?: ReactNode;
  loading?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("rounded-card border border-edge bg-panel px-6 py-5 shadow-card", className)}>
      <p className="label-caps">{label}</p>
      {loading ? (
        <Skeleton className="mt-3 h-9 w-28" />
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="tabular text-[34px] leading-tight font-bold tracking-[-0.5px] text-fg" data-numeric>
            {value}
          </p>
          {delta}
          {sub && <span className="text-sm text-fg-muted">{sub}</span>}
        </div>
      )}
    </div>
  );
}
