import { X } from "lucide-react";
import { Dialog as D, DropdownMenu as M, Popover as P, Tabs as T, Tooltip as TT } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "../../lib/cn";

const OVERLAY = "fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-[up-fade-in_150ms_ease-out]";
const POP = "z-50 rounded-control border border-edge bg-panel text-fg shadow-pop";

function CloseButton() {
  return (
    <D.Close className="rounded-control p-1.5 text-fg-muted hover:bg-panel-2 hover:text-fg" aria-label="Close">
      <X className="h-4 w-4" aria-hidden />
    </D.Close>
  );
}

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/** Centred modal dialog (focus-trapped, Esc closes). */
export function Dialog({ open, onOpenChange, title, description, children, footer, className }: ModalProps) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className={OVERLAY} />
        <D.Content
          aria-describedby={description ? undefined : undefined}
          className={cn(
            "fixed top-1/2 left-1/2 z-50 flex max-h-[85vh] w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col rounded-card border border-edge bg-panel shadow-pop",
            className,
          )}
        >
          <header className="flex items-start justify-between gap-4 border-b border-edge px-5 py-4">
            <div>
              <D.Title className="text-base font-semibold text-fg">{title}</D.Title>
              {description ? <D.Description className="mt-0.5 text-13 text-fg-muted">{description}</D.Description> : <D.Description className="sr-only">{title}</D.Description>}
            </div>
            <CloseButton />
          </header>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer && <footer className="flex justify-end gap-2 border-t border-edge px-5 py-3">{footer}</footer>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

/** Side drawer from the right, for details that keep the list in view. */
export function Sheet({ open, onOpenChange, title, description, children, footer, className }: ModalProps) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className={OVERLAY} />
        <D.Content
          className={cn("fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-edge bg-panel shadow-pop data-[state=open]:animate-slide-in", className)}
        >
          <header className="flex items-start justify-between gap-4 border-b border-edge px-5 py-4">
            <div className="min-w-0">
              <D.Title className="text-base font-semibold text-fg">{title}</D.Title>
              {description ? <D.Description className="mt-0.5 text-13 text-fg-muted">{description}</D.Description> : <D.Description className="sr-only">{title}</D.Description>}
            </div>
            <CloseButton />
          </header>
          <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <footer className="flex justify-end gap-2 border-t border-edge px-5 py-3">{footer}</footer>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export const TooltipProvider = TT.Provider;

/** Wrap any focusable element. For disabled buttons, wrap them in a <span tabIndex={0}>. */
export function Tooltip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "right" | "bottom" | "left" }) {
  if (!content) return <>{children}</>;
  return (
    <TT.Root>
      <TT.Trigger asChild>{children}</TT.Trigger>
      <TT.Portal>
        <TT.Content side={side} sideOffset={6} className="z-50 max-w-xs rounded-md bg-fg px-2.5 py-1.5 text-xs text-canvas shadow-pop">
          {content}
        </TT.Content>
      </TT.Portal>
    </TT.Root>
  );
}

export function Popover({ trigger, children, align = "start", className }: { trigger: ReactNode; children: ReactNode; align?: "start" | "center" | "end"; className?: string }) {
  return (
    <P.Root>
      <P.Trigger asChild>{trigger}</P.Trigger>
      <P.Portal>
        <P.Content align={align} sideOffset={6} className={cn(POP, "w-64 p-3", className)}>
          {children}
        </P.Content>
      </P.Portal>
    </P.Root>
  );
}

export function DropdownMenu({ trigger, children, align = "end" }: { trigger: ReactNode; children: ReactNode; align?: "start" | "center" | "end" }) {
  return (
    <M.Root>
      <M.Trigger asChild>{trigger}</M.Trigger>
      <M.Portal>
        <M.Content align={align} sideOffset={6} className={cn(POP, "min-w-48 p-1")}>
          {children}
        </M.Content>
      </M.Portal>
    </M.Root>
  );
}

const ITEM = "flex cursor-default items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-fg outline-none select-none data-[highlighted]:bg-panel-2 data-[disabled]:opacity-50";

export function MenuItem({ className, ...rest }: ComponentProps<typeof M.Item>) {
  return <M.Item className={cn(ITEM, className)} {...rest} />;
}
export function MenuCheckboxItem({ className, children, ...rest }: ComponentProps<typeof M.CheckboxItem>) {
  return (
    <M.CheckboxItem className={cn(ITEM, "pl-7", className)} {...rest}>
      <M.ItemIndicator className="absolute left-2.5 text-primary">✓</M.ItemIndicator>
      {children}
    </M.CheckboxItem>
  );
}
export function MenuLabel({ children }: { children: ReactNode }) {
  return <M.Label className="px-2.5 py-1.5 text-xs font-medium text-fg-muted">{children}</M.Label>;
}
export function MenuSeparator() {
  return <M.Separator className="my-1 h-px bg-edge" />;
}

export const Tabs = T.Root;
export function TabsList({ className, ...rest }: ComponentProps<typeof T.List>) {
  return <T.List className={cn("flex gap-1 overflow-x-auto border-b border-edge", className)} {...rest} />;
}
export function TabsTrigger({ className, ...rest }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "-mb-px border-b-2 border-transparent px-3 py-2 text-sm font-medium whitespace-nowrap text-fg-muted transition-colors hover:text-fg",
        "data-[state=active]:border-primary data-[state=active]:text-primary",
        className,
      )}
      {...rest}
    />
  );
}
export function TabsContent({ className, ...rest }: ComponentProps<typeof T.Content>) {
  return <T.Content className={cn("pt-4", className)} {...rest} />;
}
