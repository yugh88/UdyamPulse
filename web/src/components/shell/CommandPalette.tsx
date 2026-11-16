import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { Bell, Factory, FileText, Keyboard, LogOut, Moon, Search, Sun } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { navFor } from "../../lib/nav";
import { useTheme } from "../../lib/theme";
import { BandPill, SeverityPill } from "../ui";

interface AppHit {
  id: number;
  name: string;
  cluster: string;
  state: string;
  band: string | null;
}
interface AlertHit {
  id: number;
  application_id: number;
  name: string;
  severity: string;
  month: string;
}
interface FactoryHit {
  factory_id: string;
  name: string;
  cluster: string;
  sector_label: string;
}

const GROUP =
  "px-1 py-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-fg-muted";

function Item({ children, onSelect, value }: { children: ReactNode; onSelect: () => void; value: string }) {
  return (
    <Command.Item value={value} onSelect={onSelect} className="flex cursor-default items-center gap-2.5 rounded-md px-2 py-2 text-sm text-fg data-[selected=true]:bg-primary-tint">
      {children}
    </Command.Item>
  );
}

export function CommandPalette({ open, onOpenChange, onShortcuts }: { open: boolean; onOpenChange: (o: boolean) => void; onShortcuts: () => void }) {
  const { session, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const staff = !!session && session.role !== "msme";

  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  const apps = useQuery({ queryKey: ["palette", "applications"], queryFn: () => api<AppHit[]>("/applications"), enabled: open && staff, staleTime: 15_000 });
  const alerts = useQuery({ queryKey: ["palette", "alerts"], queryFn: () => api<AlertHit[]>("/alerts?status=OPEN"), enabled: open && staff, staleTime: 15_000 });
  const term = q.trim();
  const factories = useQuery({
    queryKey: ["palette", "factories", term],
    queryFn: () => api<FactoryHit[]>(`/factories?q=${encodeURIComponent(term)}&limit=6`),
    enabled: open && staff && term.length >= 2,
    staleTime: 60_000,
  });

  if (!session) return null;
  const go = (to: string) => {
    onOpenChange(false);
    nav(to);
  };
  const run = (fn: () => void) => {
    onOpenChange(false);
    fn();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Search and jump"
      overlayClassName="fixed inset-0 z-40 bg-black/40"
      contentClassName="fixed top-[15vh] left-1/2 z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-card border border-edge bg-panel shadow-pop animate-fade-in"
    >
      <div className="flex items-center gap-2 border-b border-edge px-3">
        <Search className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
        <Command.Input
          value={q}
          onValueChange={setQ}
          placeholder="Search factories, applications, alerts or pages…"
          className="h-11 w-full bg-transparent text-sm text-fg outline-none placeholder:text-fg-muted"
        />
        <kbd className="rounded border border-edge bg-panel-2 px-1.5 py-0.5 text-xs text-fg-muted">Esc</kbd>
      </div>
      <Command.List className="max-h-[50vh] overflow-y-auto p-1">
        <Command.Empty className="px-3 py-8 text-center text-sm text-fg-muted">No results.</Command.Empty>

        <Command.Group heading="Go to" className={GROUP}>
          {navFor(session.role).map((n) => (
            <Item key={n.to} value={`page ${n.label}`} onSelect={() => go(n.to)}>
              <n.icon className="h-4 w-4 text-fg-muted" aria-hidden />
              {n.label}
              {n.keys && <kbd className="ml-auto text-xs text-fg-muted">{n.keys}</kbd>}
            </Item>
          ))}
        </Command.Group>

        {staff && !!apps.data?.length && (
          <Command.Group heading="Applications" className={GROUP}>
            {apps.data.map((a) => (
              <Item key={a.id} value={`application ${a.id} ${a.name} ${a.cluster}`} onSelect={() => go(`/console/${a.id}`)}>
                <FileText className="h-4 w-4 text-fg-muted" aria-hidden />
                <span className="truncate">{a.name}</span>
                <span className="text-xs text-fg-muted">
                  #{a.id} · {a.cluster} · {a.state.replace("_", " ").toLowerCase()}
                </span>
                <span className="ml-auto">{a.band && <BandPill band={a.band} />}</span>
              </Item>
            ))}
          </Command.Group>
        )}

        {staff && !!alerts.data?.length && (
          <Command.Group heading="Open alerts" className={GROUP}>
            {alerts.data.slice(0, 8).map((a) => (
              <Item key={a.id} value={`alert ${a.id} ${a.name} ${a.severity}`} onSelect={() => go(`/cockpit?alert=${a.id}`)}>
                <Bell className="h-4 w-4 text-fg-muted" aria-hidden />
                <span className="truncate">{a.name}</span>
                <span className="text-xs text-fg-muted">{a.month}</span>
                <span className="ml-auto">
                  <SeverityPill severity={a.severity} />
                </span>
              </Item>
            ))}
          </Command.Group>
        )}

        {staff && !!factories.data?.length && (
          <Command.Group heading="Factories" className={GROUP}>
            {factories.data.map((f) => (
              <Item key={f.factory_id} value={`factory ${f.factory_id} ${f.name} ${term}`} onSelect={() => go(`/console?factory=${f.factory_id}`)}>
                <Factory className="h-4 w-4 text-fg-muted" aria-hidden />
                <span className="truncate">{f.name}</span>
                <span className="text-xs text-fg-muted">
                  {f.factory_id} · {f.sector_label} · {f.cluster}
                </span>
              </Item>
            ))}
          </Command.Group>
        )}

        <Command.Group heading="Actions" className={GROUP}>
          <Item value="action toggle theme dark light" onSelect={() => run(toggle)}>
            {theme === "dark" ? <Sun className="h-4 w-4 text-fg-muted" aria-hidden /> : <Moon className="h-4 w-4 text-fg-muted" aria-hidden />}
            Switch to {theme === "dark" ? "light" : "dark"} theme
          </Item>
          <Item value="action keyboard shortcuts help" onSelect={() => run(onShortcuts)}>
            <Keyboard className="h-4 w-4 text-fg-muted" aria-hidden />
            Keyboard shortcuts
            <kbd className="ml-auto text-xs text-fg-muted">?</kbd>
          </Item>
          <Item value="action sign out logout" onSelect={() => run(logout)}>
            <LogOut className="h-4 w-4 text-fg-muted" aria-hidden />
            Sign out
          </Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
