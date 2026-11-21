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

/**
 * The application journey. Done steps are filled forest circles with a tick; the current step is purple with a soft
 * halo and a bold label; steps still to do are hollow grey. The halo eases in over 200 ms (off with reduced motion).
 * `complete` marks the current step itself as done (e.g. a decided application has finished "Decision").
 */
export function Stepper({
  steps = JOURNEY,
  current,
  state,
  complete = false,
  className,
}: {
  steps?: Step[];
  current?: string;
  state?: string;
  complete?: boolean;
  className?: string;
}) {
  const at = steps.findIndex((s) => s.key === (current ?? state));
  const idx = complete ? at + 1 : at;
  return (
    <ol className={cn("flex items-start overflow-x-auto pb-1", className)} aria-label="Application progress">
      {steps.map((s, i) => {
        const done = i < idx;
        const active = i === idx;
        return (
          <li key={s.key} className="relative flex min-w-20 flex-1 flex-col items-center" aria-current={active ? "step" : undefined}>
            {i > 0 && <span className={cn("absolute top-[13px] right-1/2 left-[-50%] mx-6 h-[2px] rounded-full", i <= idx ? "bg-primary" : "bg-edge-2")} aria-hidden />}
            <span
              className={cn(
                "relative z-10 flex h-7 w-7 items-center justify-center rounded-full transition-colors duration-200",
                done && "bg-primary text-on-primary",
                active && "bg-purple text-on-primary motion-safe:animate-[up-halo_200ms_ease-out_forwards] shadow-[0_0_0_6px_var(--purple-tint)]",
                !done && !active && "border-2 border-edge-2 bg-panel",
              )}
            >
              {done ? <Check className="h-4 w-4" strokeWidth={3} aria-hidden /> : active ? <span className="h-2.5 w-2.5 rounded-full bg-on-primary" aria-hidden /> : null}
            </span>
            <span className={cn("mt-2 text-13 whitespace-nowrap", done && "font-medium text-fg", active && "font-bold text-purple", !done && !active && "text-fg-muted")}>
              {s.label}
              <span className="sr-only">{done ? " (done)" : active ? " (current step)" : " (to do)"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
