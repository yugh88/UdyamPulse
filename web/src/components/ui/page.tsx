import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { cn } from "../../lib/cn";

/**
 * The same header on every screen: breadcrumb (detail pages), an H1, one plain-English line under it, and at most
 * two actions on the right (one primary, one secondary).
 */
export function PageHeader({
  title,
  description,
  crumbs,
  actions,
  aside,
}: {
  title: ReactNode;
  description?: ReactNode;
  crumbs?: { label: string; to?: string }[];
  actions?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <header className="space-y-1.5">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-13 text-fg-muted">
          {crumbs.map((c, i) => (
            <span key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden />}
              {c.to ? (
                <Link to={c.to} className="truncate hover:text-fg">
                  {c.label}
                </Link>
              ) : (
                <span className="truncate" aria-current="page">
                  {c.label}
                </span>
              )}
            </span>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-title font-bold tracking-[-0.5px] text-fg">{title}</h1>
            {aside}
          </div>
          {description && <p className="mt-1 text-sm text-fg-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2.5">{actions}</div>}
      </div>
    </header>
  );
}

/** Tab state kept in the URL (`?tab=`), so a reload or a shared link opens the same tab. */
export function useUrlTab<T extends string>(allowed: readonly T[], fallback: T, param = "tab"): [T, (t: string) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(param);
  const value = (allowed as readonly string[]).includes(raw ?? "") ? (raw as T) : fallback;
  const set = (t: string) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p);
        if (t === fallback) next.delete(param);
        else next.set(param, t);
        return next;
      },
      { replace: true },
    );
  return [value, set];
}

/** A small segmented control: one choice from a few, for switching a chart or a list view. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: { value: T; label: ReactNode }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex flex-wrap gap-1 rounded-control bg-panel-2 p-1", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-3 py-1.5 text-13 font-medium transition-colors duration-150",
            value === o.value ? "bg-panel text-fg shadow-card" : "text-fg-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
