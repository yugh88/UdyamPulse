import { BadgeCheck, Factory, FileCheck2, Landmark, TrendingDown, TrendingUp, Users, type LucideIcon } from "lucide-react";
import { cn } from "../../lib/cn";
import { signed } from "../../lib/format";
import { plainReasons } from "../../lib/reasons";
import type { Reason } from "../../lib/types";

const PILLAR_ICON: Record<string, LucideIcon> = {
  order_book: TrendingUp,
  cash_flow: Landmark,
  production: Factory,
  receivables: Users,
  compliance: FileCheck2,
};

/** A plain-language title for a single reason (its theme, helps or hurts). */
export function reasonTitle(r: Reason): string {
  return plainReasons([r])[0]!.title;
}

/** Top reasons in plain words: one row per theme (never a repeated title), an icon tile and the points it moves. */
export function WhyScore({ reasons, limit = 4 }: { reasons: Reason[]; limit?: number }) {
  const top = plainReasons(reasons).slice(0, limit);
  return (
    <ol className="divide-y divide-edge">
      {top.map((r) => {
        const Icon = PILLAR_ICON[r.pillar] ?? (r.helps ? BadgeCheck : TrendingDown);
        return (
          <li key={r.key} className="flex items-center gap-4 py-3.5 first:pt-0 last:pb-0">
            <span
              className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-control", r.helps ? "bg-success-tint text-success" : "bg-warning-tint text-warning")}
              aria-hidden
            >
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold text-fg">{r.title}</p>
              <p className="text-13 text-fg-muted">{r.detail}</p>
            </div>
            <span className={cn("tabular shrink-0 text-base font-bold", r.helps ? "text-success" : "text-warning")}>
              {signed(r.points, 0)}
              <span className="sr-only">{r.helps ? " points, helps the score" : " points, lowers the score"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
