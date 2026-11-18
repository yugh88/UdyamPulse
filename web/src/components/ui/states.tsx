import { Inbox, RefreshCw, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Button } from "./button";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-md bg-[linear-gradient(90deg,var(--surface-2)_25%,var(--border)_50%,var(--surface-2)_75%)] bg-[length:200%_100%] animate-[up-shimmer_1.4s_linear_infinite]",
        className,
      )}
    />
  );
}

/** Placeholder rows for a table or list while it loads. */
export function SkeletonRows({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading" className={cn("space-y-2", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, description, action, className }: { icon?: ReactNode; title: string; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-panel-2 text-fg-muted">{icon ?? <Inbox className="h-6 w-6" aria-hidden />}</div>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {description && <p className="mt-1 max-w-sm text-13 text-fg-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", error, onRetry, className }: { title?: string; error?: unknown; onRetry?: () => void; className?: string }) {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : null;
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-danger-tint text-danger">
        <TriangleAlert className="h-6 w-6" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {message && <p className="mt-1 max-w-sm text-13 text-fg-muted">{message}</p>}
      {onRetry && (
        <Button className="mt-4" onClick={onRetry} icon={<RefreshCw className="h-4 w-4" aria-hidden />}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Inline error banner for form and action failures. */
export function ErrorNote({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return (
    <p role="alert" className="flex items-start gap-2 rounded-control bg-danger-tint px-3 py-2 text-sm text-danger">
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      {error}
    </p>
  );
}
