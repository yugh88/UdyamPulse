import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, ChevronDown, ChevronsUpDown, Keyboard, Moon, PanelLeft, Search, Sun } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { DEMO_PASSWORD, homeFor, PERSONAS, ROLE_LABEL, useAuth, type Role } from "../../lib/auth";
import { useLiveChanges } from "../../lib/changes";
import { cn } from "../../lib/cn";
import { useHotkeys } from "../../lib/hotkeys";
import { navFor } from "../../lib/nav";
import { useTheme } from "../../lib/theme";
import { monthLabel } from "../../lib/time";
import type { AlertRow, AppStats } from "../../lib/types";
import { Button, Dialog, DropdownMenu, MenuItem, MenuLabel, MenuSeparator, Sheet, SkeletonRows, Tooltip } from "../ui";
import { CommandPalette } from "./CommandPalette";
import { FirstVisitNotice, PrototypeChip } from "./PrototypeBanner";
import { GuideLauncher } from "../../features/demo/DemoGuide";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const MOD = isMac ? "⌘" : "Ctrl";

function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <img src="/icon.svg" alt="" className="h-8 w-8 rounded-[9px]" />
      <span className="text-[17px] font-bold tracking-[-0.3px] text-fg">
        Udyam<span className="text-primary">Pulse</span>
      </span>
    </span>
  );
}

/** Pink counts on the sidebar: only things that need action (applications waiting on you, open alerts). */
function useNavCounts(role: Role) {
  const staff = role !== "msme";
  const apps = useQuery({
    queryKey: ["nav-counts", "applications"],
    queryFn: () => api<AppStats>("/applications/stats"),
    enabled: role === "rm" || role === "credit_officer",
    staleTime: 30_000,
  });
  const alerts = useQuery({
    queryKey: ["nav-counts", "alerts"],
    queryFn: () => api<AlertRow[]>("/alerts?status=OPEN"),
    enabled: staff,
    staleTime: 30_000,
  });
  return {
    applications: apps.data?.tiles?.waiting_on_you?.value ?? null,
    alerts: alerts.data ? alerts.data.length : null,
  };
}

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  const { session } = useAuth();
  const counts = useNavCounts(session!.role);
  return (
    <nav aria-label="Main" className="flex flex-col gap-1 px-3">
      {navFor(session!.role).map((n) => {
        const count = n.count ? counts[n.count] : null;
        return (
          <NavLink
            key={n.to}
            to={n.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex h-11 items-center gap-3 rounded-[10px] px-3 text-[15px] transition-colors duration-150",
                isActive ? "bg-primary-tint font-semibold text-primary" : "font-medium text-fg-muted hover:bg-panel-2 hover:text-fg",
              )
            }
          >
            <n.icon className="h-5 w-5 shrink-0" aria-hidden />
            <span className="flex-1">{n.label}</span>
            {count ? (
              <span className="tabular rounded-full bg-brand-tint px-2 py-px text-xs font-bold text-brand">
                {count}
                <span className="sr-only">{n.count === "alerts" ? " open alerts" : " need your action"}</span>
              </span>
            ) : null}
          </NavLink>
        );
      })}
    </nav>
  );
}

function ClockChip() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["clock"], queryFn: () => api<{ sim_date: string; data_month: string }>("/sim/clock"), staleTime: 30_000 });
  useEffect(() => {
    const refresh = () => qc.invalidateQueries({ queryKey: ["clock"] });
    window.addEventListener("sim-advanced", refresh);
    return () => window.removeEventListener("sim-advanced", refresh);
  }, [qc]);
  if (!data) return null;
  return (
    <Tooltip content={`Simulated demo clock. Data is visible through ${monthLabel(data.data_month)}.`}>
      <span tabIndex={0} className="tabular inline-flex h-9 items-center gap-1.5 rounded-full border border-edge-2 bg-panel px-3.5 text-13 font-medium text-fg">
        <CalendarDays className="h-4 w-4 text-fg-muted" aria-hidden />
        <span className="sr-only">Simulated date</span>
        {monthLabel(data.sim_date)}
      </span>
    </Tooltip>
  );
}

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");

function AccountMenu({ compact, onShortcuts }: { compact?: boolean; onShortcuts: () => void }) {
  const { session, login } = useAuth();
  const nav = useNavigate();
  const [switching, setSwitching] = useState(false);
  if (!session) return null;

  async function switchTo(username: string) {
    if (username === session!.username || switching) return;
    setSwitching(true);
    try {
      const s = await login(username, DEMO_PASSWORD);
      nav(homeFor(s.role));
      toast.success(`Now viewing as ${ROLE_LABEL[s.role]}`);
    } catch (e) {
      toast.error(`Could not switch role: ${(e as Error).message}`);
    } finally {
      setSwitching(false);
    }
  }

  return (
    <DropdownMenu
      align={compact ? "end" : "start"}
      trigger={
        <button
          type="button"
          aria-label={`${compact ? "Switch role. " : ""}Account menu for ${session.display_name}, ${ROLE_LABEL[session.role]}`}
          className={cn(
            "flex items-center text-left transition-colors hover:bg-panel-2",
            compact
              ? "h-9 gap-2 rounded-full border border-edge-2 bg-panel pr-3 pl-1 text-13 font-semibold text-fg hover:border-edge-strong"
              : "w-full gap-3 rounded-[10px] px-2.5 py-2",
          )}
        >
          <span
            className={cn("flex shrink-0 items-center justify-center rounded-full bg-purple-tint font-bold text-purple", compact ? "h-7 w-7 text-xs" : "h-9 w-9 text-13")}
            aria-hidden
          >
            {initials(session.display_name)}
          </span>
          {/* On the owner's screen this is the only way back to the bank roles, so it says so. */}
          {compact && (
            <>
              <span className="whitespace-nowrap">Switch role</span>
              <ChevronDown className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
            </>
          )}
          {!compact && (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm leading-snug font-semibold text-fg">{session.display_name}</span>
              <span className="block truncate text-13 text-fg-muted">{ROLE_LABEL[session.role]}</span>
            </span>
          )}
          {!compact && <ChevronsUpDown className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />}
        </button>
      }
    >
      <MenuLabel>
        {session.display_name} · {session.tenant_name}
      </MenuLabel>
      <MenuSeparator />
      <MenuLabel>View the demo as</MenuLabel>
      {PERSONAS.map((p) => (
        <MenuItem key={p.username} disabled={switching} onSelect={() => switchTo(p.username)}>
          <span className="flex-1">{p.title}</span>
          {p.username === session.username && <span className="text-xs text-primary">current</span>}
        </MenuItem>
      ))}
      <MenuSeparator />
      <MenuItem onSelect={onShortcuts}>
        <Keyboard className="h-4 w-4 text-fg-muted" aria-hidden />
        Keyboard shortcuts
      </MenuItem>
    </DropdownMenu>
  );
}

const SHORTCUTS: [string, string][] = [
  [`${MOD} K`, "Search and jump to any factory, application or alert"],
  ["g c", "Go to applications"],
  ["g a", "Go to early-warning alerts"],
  ["g p", "Go to the portfolio"],
  ["g g", "Go to governance"],
  ["g s", "Go to system health"],
  ["t", "Toggle light and dark theme"],
  ["?", "Show this sheet"],
];

export function AppShell() {
  const { session } = useAuth();
  const { theme, toggle } = useTheme();
  const nav = useNavigate();
  const [mobileNav, setMobileNav] = useState(false);
  const [palette, setPalette] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);
  useLiveChanges();

  const go = (to: string) => () => {
    if (session && navFor(session.role).some((n) => n.to === to)) nav(to);
  };
  useHotkeys({
    "mod+k": () => setPalette((o) => !o),
    "/": () => setPalette(true),
    "?": () => setShortcuts(true),
    t: toggle,
    "g c": go("/console"),
    "g a": go("/alerts"),
    "g p": go("/portfolio"),
    "g g": go("/governance"),
    "g s": go("/system"),
  });

  if (!session) return null;
  const msme = session.role === "msme";

  return (
    <div className="flex min-h-screen bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-control focus:bg-panel focus:px-3 focus:py-2 focus:shadow-pop"
      >
        Skip to content
      </a>

      {!msme && (
        <aside aria-label="Sidebar" className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-edge bg-panel md:flex">
          <div className="flex h-[76px] items-center px-5">
            <Logo />
          </div>
          <div className="flex-1 overflow-y-auto py-3">
            <SideNav />
          </div>
          <div className="mx-3 border-t border-edge py-3">
            <AccountMenu onShortcuts={() => setShortcuts(true)} />
          </div>
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2.5 border-b border-edge bg-canvas/95 px-4 backdrop-blur sm:px-8">
          {msme ? (
            <Logo />
          ) : (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden"
                aria-label="Open navigation"
                onClick={() => setMobileNav(true)}
                icon={<PanelLeft className="h-5 w-5" aria-hidden />}
              />
              <button
                type="button"
                onClick={() => setPalette(true)}
                className="flex h-10 min-w-0 items-center gap-2.5 rounded-control border border-edge-2 bg-panel px-3.5 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-fg sm:w-[min(470px,40vw)]"
              >
                <Search className="h-[18px] w-[18px] shrink-0" aria-hidden />
                <span className="hidden truncate sm:inline">Search factory or application</span>
                <span className="sr-only sm:hidden">Search</span>
                <kbd className="ml-auto hidden rounded-md border border-edge bg-panel-2 px-1.5 text-xs font-medium sm:inline">{MOD}K</kbd>
              </button>
            </>
          )}

          <div className="ml-auto flex items-center gap-2">
            <PrototypeChip />
            {/* The owner's phone keeps only what they need in the top bar. */}
            <span className={cn(msme && "hidden sm:inline-flex")}>
              <ClockChip />
            </span>
            <GuideLauncher className="hidden lg:inline-flex" />
            <Tooltip content={`Switch to ${theme === "dark" ? "light" : "dark"} theme (t)`}>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggle}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                icon={theme === "dark" ? <Sun className="h-[18px] w-[18px]" aria-hidden /> : <Moon className="h-[18px] w-[18px]" aria-hidden />}
              />
            </Tooltip>
            {msme && <AccountMenu compact onShortcuts={() => setShortcuts(true)} />}
          </div>
        </header>
        <FirstVisitNotice />

        <main id="main" className={cn("mx-auto w-full flex-1 px-4 py-[26px] sm:px-8", msme ? "max-w-5xl" : "max-w-[1680px]")}>
          <Suspense fallback={<SkeletonRows rows={8} className="mt-4" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      <Sheet open={mobileNav} onOpenChange={setMobileNav} title={<Logo />} className="right-auto left-0 max-w-64 border-r border-l-0 data-[state=open]:animate-none">
        <SideNav onNavigate={() => setMobileNav(false)} />
        <div className="mt-6 border-t border-edge pt-3">
          <AccountMenu onShortcuts={() => setShortcuts(true)} />
        </div>
      </Sheet>
      <CommandPalette open={palette} onOpenChange={setPalette} onShortcuts={() => setShortcuts(true)} />
      <Dialog open={shortcuts} onOpenChange={setShortcuts} title="Keyboard shortcuts">
        <dl className="space-y-2.5">
          {SHORTCUTS.map(([k, d]) => (
            <div key={k} className="flex items-center justify-between gap-4">
              <dd className="text-sm text-fg">{d}</dd>
              <dt>
                <kbd className="rounded border border-edge bg-panel-2 px-2 py-1 text-xs whitespace-nowrap text-fg-muted">{k}</kbd>
              </dt>
            </div>
          ))}
        </dl>
      </Dialog>
    </div>
  );
}
