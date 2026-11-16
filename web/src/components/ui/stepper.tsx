import { Check } from "lucide-react";
import { cn } from "../../lib/cn";

export interface Step {
  key: string;
  label: string;
}

export const JOURNEY: Step[] = [
  { key: "APPLIED", label: "Applied" },
  { key: "CONSENTED", label: "Consented" },
  { key: "SCORED", label: "Scored" },
  { key: "MEMO_DRAFTED", label: "Memo" },
  { key: "DECIDED", label: "Decision" },
  { key: "DISBURSED", label: "Disbursed" },
  { key: "MONITORING", label: "Monitoring" },
];

/** Horizontal progress through ordered steps. Done steps show a tick, the current step is announced. */
export function Stepper({ steps = JOURNEY, current, state, className }: { steps?: Step[]; current?: string; state?: string; className?: string }) {
  const idx = steps.findIndex((s) => s.key === (current ?? state));
  return (
    <ol className={cn("flex items-center overflow-x-auto", className)} aria-label="Progress">
      {steps.map((s, i) => {
        const done = i < idx;
        const active = i === idx;
        return (
          <li key={s.key} className="flex min-w-0 flex-1 items-center last:flex-none" aria-current={active ? "step" : undefined}>
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  "tabular flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  done && "bg-success-tint text-success",
                  active && "bg-primary text-on-primary",
                  !done && !active && "border border-edge bg-panel-2 text-fg-muted",
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" aria-hidden /> : i + 1}
              </span>
              <span className={cn("text-13 whitespace-nowrap", active ? "font-semibold text-fg" : "text-fg-muted")}>
                {s.label}
                {done && <span className="sr-only"> (done)</span>}
              </span>
            </span>
            {i < steps.length - 1 && <span className={cn("mx-3 h-px min-w-4 flex-1", done ? "bg-success" : "bg-edge")} aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}
