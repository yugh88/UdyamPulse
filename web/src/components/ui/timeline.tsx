import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import type { Tone } from "./badge";

export interface TimelineItem {
  id: string | number;
  title: ReactNode;
  meta?: ReactNode;
  body?: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
}

const DOT: Record<Tone, string> = {
  neutral: "bg-panel-2 text-fg-muted",
  primary: "bg-primary-tint text-primary",
  success: "bg-success-tint text-success",
  warning: "bg-warning-tint text-warning",
  danger: "bg-danger-tint text-danger",
  info: "bg-info-tint text-info",
  brand: "bg-brand-tint text-brand",
  purple: "bg-purple-tint text-purple",
};

export function Timeline({ items, className }: { items: TimelineItem[]; className?: string }) {
  return (
    <ol className={cn("relative", className)}>
      {items.map((it, i) => (
        <li key={it.id} className="relative flex gap-3 pb-4 last:pb-0">
          {i < items.length - 1 && <span className="absolute top-7 bottom-0 left-3 w-px bg-edge" aria-hidden />}
          <span className={cn("z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full", DOT[it.tone ?? "neutral"])} aria-hidden>
            {it.icon ?? <span className="h-1.5 w-1.5 rounded-full bg-current" />}
          </span>
          <div className="min-w-0 flex-1 pt-0.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <p className="text-13 font-medium text-fg">{it.title}</p>
              {it.meta && <p className="tabular text-xs text-fg-muted">{it.meta}</p>}
            </div>
            {it.body && <div className="mt-0.5 text-13 text-fg-muted">{it.body}</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}
