import { BadgeCheck, Factory, FileCheck2, Landmark, TrendingDown, TrendingUp, Users, type LucideIcon } from "lucide-react";
import { cn } from "../../lib/cn";
import { signed } from "../../lib/format";
import type { Reason } from "../../lib/types";

const PILLAR_ICON: Record<string, LucideIcon> = {
  order_book: TrendingUp,
  cash_flow: Landmark,
  production: Factory,
  receivables: Users,
  compliance: FileCheck2,
};

/** A plain-language title for a reason: what it means for the factory, with the technical measure underneath. */
export function reasonTitle(r: Reason): string {
  const helps = r.points >= 0;
  const f = r.feature;
  if (f.startsWith("bounces")) return helps ? "No payment bounces" : "Payments are bouncing";
  if (f.startsWith("gst_delay") || f.startsWith("gst_late") || f.startsWith("gst_consecutive")) return helps ? "GST filed on time" : "GST filed late";
  if (f.startsWith("gst_bank_mismatch")) return helps ? "Sales match bank deposits" : "Sales and bank deposits differ";
  if (f.startsWith("top_buyer_share") || f.startsWith("buyer_hhi") || f === "n_buyers") return helps ? "Sales spread across buyers" : "One big buyer";
  if (f.startsWith("days_to_pay")) return helps ? "Buyers pay on time" : "Buyers are paying slowly";
  if (f.startsWith("epfo")) return helps ? "Workforce is steady" : "Workforce is shrinking";
  if (f === "vintage_years") return helps ? "Established business" : "Young business";
  if (f.startsWith("kwh")) return helps ? "Factory is running" : "Power use is falling";
  switch (r.pillar) {
    case "order_book":
      return helps ? "Orders are growing" : "Orders are slowing";
    case "cash_flow":
      return helps ? "Steady bank inflows" : "Cash flow is tight";
    case "production":
      return helps ? "Factory is running" : "Production is slowing";
    case "receivables":
      return helps ? "Buyers pay well" : "Buyer risk";
    default:
      return helps ? "Records in order" : "Compliance slips";
  }
}

/** Top reasons in plain words, each with an icon tile and the points it adds or removes. */
export function WhyScore({ reasons, limit = 4 }: { reasons: Reason[]; limit?: number }) {
  const top = [...reasons].sort((a, b) => Math.abs(b.points) - Math.abs(a.points)).slice(0, limit);
  return (
    <ol className="divide-y divide-edge">
      {top.map((r) => {
        const helps = r.points >= 0;
        const Icon = PILLAR_ICON[r.pillar] ?? (helps ? BadgeCheck : TrendingDown);
        return (
          <li key={r.feature} className="flex items-center gap-4 py-3.5 first:pt-0 last:pb-0">
            <span
              className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-control", helps ? "bg-success-tint text-success" : "bg-warning-tint text-warning")}
              aria-hidden
            >
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold text-fg">{reasonTitle(r)}</p>
              <p className="text-13 text-fg-muted">{r.text}</p>
            </div>
            <span className={cn("tabular shrink-0 text-base font-bold", helps ? "text-success" : "text-warning")}>
              {signed(r.points, 0)}
              <span className="sr-only">{helps ? " points, helps the score" : " points, lowers the score"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
