import { ChevronDown, CircleAlert } from "lucide-react";
import { useId, type InputHTMLAttributes, type ReactElement, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes, cloneElement } from "react";
import { cn } from "../../lib/cn";

const CONTROL =
  "w-full rounded-control border border-edge-strong bg-panel px-3 text-sm text-fg placeholder:text-fg-muted transition-colors " +
  "hover:border-fg-muted focus:border-primary focus:outline-2 focus:outline-offset-0 focus:outline-primary/30 " +
  "disabled:cursor-not-allowed disabled:bg-panel-2 disabled:opacity-60 aria-[invalid=true]:border-danger";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(CONTROL, "h-9", className)} {...rest} />;
}

export function Textarea({ className, rows = 3, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} className={cn(CONTROL, "py-2 leading-normal", className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="relative block">
      <select className={cn(CONTROL, "h-9 appearance-none pr-8", className)} {...rest}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 h-4 w-4 -translate-y-1/2 text-fg-muted" aria-hidden />
    </span>
  );
}

/** Label + control + hint + inline validation message, wired with aria attributes. */
export function Field({
  label,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  children: ReactElement<Record<string, unknown>>;
  className?: string;
}) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="block text-13 font-medium text-fg">
        {label}
        {required && (
          <span className="text-danger" aria-hidden>
            {" "}
            *
          </span>
        )}
      </label>
      {cloneElement(children, { id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy, required })}
      {error ? (
        <p id={`${id}-error`} role="alert" className="flex items-center gap-1 text-xs text-danger">
          <CircleAlert className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-xs text-fg-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
