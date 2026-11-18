import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

export function Card({
  title,
  description,
  actions,
  children,
  className,
  padded = true,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={cn("rounded-card border border-edge bg-panel shadow-card", padded && "p-5", className)}>
      {(title || actions) && (
        <header className={cn("flex items-start justify-between gap-3", padded ? "mb-4" : "px-5 pt-5 pb-3")}>
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-fg">{title}</h2>}
            {description && <p className="mt-0.5 text-13 text-fg-muted">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
