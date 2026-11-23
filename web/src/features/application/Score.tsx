import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "../../lib/cn";
import { PILLAR_COLORS, signed } from "../../lib/format";
import { plainDetail } from "../../lib/reasons";
import type { Pillar, Reason } from "../../lib/types";

/** Top reasons as plain-language cards. Each shows direction with an arrow, a signed number and a bar. */
export function ReasonCards({ reasons }: { reasons: Reason[] }) {
  const max = Math.max(10, ...reasons.map((r) => Math.abs(r.points)));
  return (
    <ol className="space-y-2">
      {reasons.map((r, i) => {
        const up = r.points >= 0;
        return (
          <li key={r.feature} className="rounded-control border border-edge px-3 py-2.5">
            <div className="flex items-start gap-2.5">
              <span className="tabular mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-panel-2 text-xs font-medium text-fg-muted">{i + 1}</span>
              <p className="flex-1 text-13 text-fg">{plainDetail(r)}</p>
              <span className={cn("tabular inline-flex shrink-0 items-center gap-0.5 text-13 font-semibold", up ? "text-success" : "text-danger")}>
                {up ? <ArrowUp className="h-3.5 w-3.5" aria-hidden /> : <ArrowDown className="h-3.5 w-3.5" aria-hidden />}
                {signed(r.points, 1)}
                <span className="sr-only">{up ? " points, helps the score" : " points, hurts the score"}</span>
              </span>
            </div>
            <div className="mt-2 ml-7 h-1.5 overflow-hidden rounded-full bg-panel-2" aria-hidden>
              <div className={cn("h-full rounded-full", up ? "bg-success" : "bg-danger")} style={{ width: `${(Math.abs(r.points) / max) * 100}%` }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Five pillars as diverging bars around zero: right adds score points, left removes them. */
export function PillarBars({ pillars }: { pillars: Pillar[] }) {
  const max = Math.max(10, ...pillars.map((p) => Math.abs(p.points)));
  return (
    <div>
      <ul className="space-y-3">
        {pillars.map((p) => {
          const w = (Math.abs(p.points) / max) * 50;
          const up = p.points >= 0;
          return (
            <li key={p.pillar}>
              <div className="flex items-baseline justify-between gap-2 text-13">
                <span className="flex items-center gap-2 text-fg">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: PILLAR_COLORS[p.pillar] }} aria-hidden />
                  {p.label}
                </span>
                <span className={cn("tabular inline-flex items-center gap-0.5 font-semibold", up ? "text-success" : "text-danger")}>
                  {up ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />}
                  {signed(p.points, 1)}
                </span>
              </div>
              <div className="relative mt-1.5 h-2 rounded-full bg-panel-2" aria-hidden>
                <div className="absolute inset-y-0 left-1/2 w-px bg-edge-strong" />
                <div className={cn("absolute inset-y-0 rounded-full", up ? "bg-success" : "bg-danger")} style={{ width: `${w}%`, left: up ? "50%" : `${50 - w}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-fg-muted">Score points each pillar adds or removes (SHAP).</p>
    </div>
  );
}
