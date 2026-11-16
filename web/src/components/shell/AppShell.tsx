import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, ChevronDown, ChevronRight, ChevronsLeft, ChevronsRight, Clock, Keyboard, LogOut, Moon, PanelLeft, Search, Sun, UserRound } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { DEMO_PASSWORD, homeFor, PERSONAS, ROLE_LABEL, useAuth } from "../../lib/auth";
import { cn } from "../../lib/cn";
import { useHotkeys } from "../../lib/hotkeys";
import { crumbs, navFor } from "../../lib/nav";
import { useTheme } from "../../lib/theme";
import { Badge, Button, Dialog, DropdownMenu, MenuItem, MenuLabel, MenuSeparator, Sheet, SkeletonRows, Tooltip } from "../ui";
import { CommandPalette } from "./CommandPalette";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const MOD = isMac ? "⌘" : "Ctrl";

function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <img src="/icon.svg" alt="" className="h-7 w-7 rounded-md" />
      {!collapsed && <span className="text-base font-semibold tracking-tight text-fg">UdyamPulse</span>}
    </span>
  );
}

function SideNav({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { session } = useAuth();
  if (!session) return null;
  return (
    <nav aria-label="Main" className="flex flex-col gap-1 px-2">
      {navFor(session.role).map((n) => {
        const link = (
          <NavLink
            key={n.to}
            to={n.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex h-9 items-center gap-3 rounded-control px-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-primary-tint text-primary" : "text-fg-muted hover:bg-panel-2 hover:text-fg",
                collapsed && "justify-center px-0",
              )
            }
          >
            <n.icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
            {collapsed ? <span className="sr-only">{n.label}</span> : n.label}
          </NavLink>
        );
        return collapsed ? (
          <Tooltip key={n.to} content={n.label} side="right">
            {link}
          </Tooltip>
        ) : (
          link
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
    <Tooltip content={`Simulated demo clock. Data is visible through ${data.data_month}.`}>
      <span tabIndex={0} className="tabular hidden h-8 items-center gap-1.5 rounded-control border border-edge bg-panel px-2.5 text-xs text-fg-muted sm:inline-flex">
        <Clock className="h-3.5 w-3.5" aria-hidden />
        <span className="sr-only">Simulated date</span>
        <span className="font-medium text-fg">{data.sim_date}</span>
      </span>
    </Tooltip>
  );
}

const SHORTCUTS: [string, string][] = [
  [`${MOD} K`, "Search and jump to any factory, application or alert"],
  ["g c", "Go to the credit console"],
  ["g p", "Go to the portfolio risk cockpit"],
  ["g g", "Go to governance"],
  ["t", "Toggle light and dark theme"],
  ["?", "Show this sheet"],
];

export function AppShell() {
  const { session, login, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const nav = useNavigate();
  const loc = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("up_sidebar") === "collapsed");
  const [mobileNav, setMobileNav] = useState(false);
  const [palette, setPalette] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);
  const [switching, setSwitching] = useState(false);

  const allowed = (to: string) => !!session && navFor(session.role).some((n) => n.to === to);
  useHotkeys({
    "mod+k": () => setPalette((o) => !o),
    "/": () => setPalette(true),
    "?": () => setShortcuts(true),
    t: toggle,
    "g c": () => allowed("/console") && nav("/console"),
    "g p": () => allowed("/cockpit") && nav("/cockpit"),
    "g g": () => allowed("/governance") && nav("/governance"),
  });

  if (!session) return null;
  const trail = crumbs(loc.pathname);
  const msme = session.role === "msme";

  async function switchTo(username: string) {
    if (username === session!.username || switching) return;
    setSwitching(true);
    try {
      const s = await login(username, DEMO_PASSWORD);
      nav(homeFor(s.role));
      toast.success(`Now signed in as ${ROLE_LABEL[s.role]}`);
    } catch (e) {
      toast.error(`Could not switch role: ${(e as Error).message}`);
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-control focus:bg-panel focus:px-3 focus:py-2 focus:shadow-pop"
      >
        Skip to content
      </a>

      {!msme && (
        <aside className={cn("sticky top-0 hidden h-screen shrink-0 flex-col border-r border-edge bg-panel transition-[width] duration-200 md:flex", collapsed ? "w-14" : "w-56")}>
          <div className={cn("flex h-14 items-center border-b border-edge", collapsed ? "justify-center" : "px-4")}>
            <Logo collapsed={collapsed} />
          </div>
          <div className="flex-1 overflow-y-auto py-3">
            <SideNav collapsed={collapsed} />
          </div>
          {!collapsed && session.tenant_name && (
            <p className="truncate px-4 pb-2 text-xs text-fg-muted" title="Your bank. You see only this bank's data.">
              <Building2 className="mr-1.5 inline h-3.5 w-3.5" aria-hidden />
              {session.tenant_name}
            </p>
          )}
          <div className="border-t border-edge p-2">
            <Button
              variant="ghost"
              size="sm"
              className={cn("w-full", !collapsed && "justify-start")}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              onClick={() => {
                localStorage.setItem("up_sidebar", collapsed ? "open" : "collapsed");
                setCollapsed(!collapsed);
              }}
              icon={collapsed ? <ChevronsRight className="h-4 w-4" aria-hidden /> : <ChevronsLeft className="h-4 w-4" aria-hidden />}
            >
              {!collapsed && "Collapse"}
            </Button>
          </div>
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-edge bg-panel/95 px-3 backdrop-blur sm:px-5">
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
              <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1 text-sm sm:flex">
                {trail.map((c, i) => (
                  <span key={c.label} className="flex min-w-0 items-center gap-1">
                    {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden />}
                    {c.to ? (
                      <Link to={c.to} className="truncate text-fg-muted hover:text-fg">
                        {c.label}
                      </Link>
                    ) : (
                      <span className="truncate font-medium text-fg" aria-current="page">
                        {c.label}
                      </span>
                    )}
                  </span>
                ))}
              </nav>
            </>
          )}

          <div className="ml-auto flex items-center gap-1.5">
            {!msme && (
              <button
                type="button"
                onClick={() => setPalette(true)}
                className="flex h-8 items-center gap-2 rounded-control border border-edge bg-panel-2 px-2.5 text-13 text-fg-muted hover:border-edge-strong hover:text-fg sm:w-56"
              >
                <Search className="h-4 w-4" aria-hidden />
                <span className="hidden sm:inline">Search…</span>
                <span className="sr-only sm:hidden">Search</span>
                <kbd className="ml-auto hidden rounded border border-edge bg-panel px-1.5 text-xs sm:inline">{MOD} K</kbd>
              </button>
            )}
            <ClockChip />
            <Tooltip content={`Switch to ${theme === "dark" ? "light" : "dark"} theme (t)`}>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggle}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                icon={theme === "dark" ? <Sun className="h-[18px] w-[18px]" aria-hidden /> : <Moon className="h-[18px] w-[18px]" aria-hidden />}
              />
            </Tooltip>

            <DropdownMenu
              trigger={
                <Button variant="ghost" size="sm" className="gap-1.5 pl-1.5" aria-label={`Account menu for ${session.display_name}`}>
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-tint text-brand">
                    <UserRound className="h-3.5 w-3.5" aria-hidden />
                  </span>
                  <span className="hidden max-w-40 truncate text-fg lg:inline">{session.display_name}</span>
                  <Badge tone="neutral" className="hidden sm:inline-flex">
                    {ROLE_LABEL[session.role]}
                  </Badge>
                  <ChevronDown className="h-3.5 w-3.5" aria-hidden />
                </Button>
              }
            >
              <MenuLabel>
                {session.display_name} · {session.tenant_name}
              </MenuLabel>
              <MenuSeparator />
              <MenuLabel>Switch role (demo only)</MenuLabel>
              {PERSONAS.map((p) => (
                <MenuItem key={p.username} disabled={switching} onSelect={() => switchTo(p.username)}>
                  <span className="flex-1">{p.title}</span>
                  {p.username === session.username && <span className="text-xs text-primary">current</span>}
                </MenuItem>
              ))}
              <MenuSeparator />
              <MenuItem onSelect={() => setShortcuts(true)}>
                <Keyboard className="h-4 w-4 text-fg-muted" aria-hidden />
                Keyboard shortcuts
              </MenuItem>
              <MenuItem
                onSelect={() => {
                  logout();
                  nav("/login");
                }}
              >
                <LogOut className="h-4 w-4 text-fg-muted" aria-hidden />
                Sign out
              </MenuItem>
            </DropdownMenu>
          </div>
        </header>

        <main id="main" className={cn("mx-auto w-full flex-1 px-3 py-5 sm:px-6", msme ? "max-w-5xl" : "max-w-[1440px]")}>
          <Suspense fallback={<SkeletonRows rows={8} className="mt-4" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      <Sheet open={mobileNav} onOpenChange={setMobileNav} title={<Logo />} className="right-auto left-0 max-w-64 border-r border-l-0 data-[state=open]:animate-none">
        <SideNav collapsed={false} onNavigate={() => setMobileNav(false)} />
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
