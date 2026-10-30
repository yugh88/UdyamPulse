import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/console", label: "Credit console", roles: ["rm", "credit_officer"] },
  { to: "/cockpit", label: "Risk cockpit", roles: ["rm", "credit_officer", "risk"] },
  { to: "/governance", label: "Governance", roles: ["risk"] },
  { to: "/msme", label: "MSME app", roles: ["msme"] },
];

export function Layout() {
  const { session, logout } = useAuth();
  const nav = useNavigate();
  const [clock, setClock] = useState<{ sim_date: string; data_month: string } | null>(null);

  useEffect(() => {
    const load = () => api("/sim/clock").then(setClock).catch(() => undefined);
    load();
    window.addEventListener("sim-advanced", load);
    return () => window.removeEventListener("sim-advanced", load);
  }, []);

  if (!session) return null;
  return (
    <div className="min-h-screen">
      <header className="bg-navy text-white">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <div className="flex items-center gap-2">
            <img src="/icon.svg" alt="" className="h-7 w-7" />
            <span className="text-lg font-bold">UdyamPulse</span>
          </div>
          <nav className="flex gap-1">
            {NAV.filter((n) => n.roles.includes(session.role)).map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) => `rounded-md px-3 py-1.5 text-sm font-medium ${isActive ? "bg-white/15" : "text-white/75 hover:text-white"}`}
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4 text-xs">
            {clock && (
              <span className="rounded-md bg-white/10 px-2 py-1" title="Simulated clock (demo)">
                Sim date <b>{clock.sim_date}</b> · data through <b>{clock.data_month}</b>
              </span>
            )}
            <span className="text-white/80">
              {session.display_name} <span className="rounded bg-magenta px-1.5 py-0.5 font-semibold">{session.role}</span>
            </span>
            <button
              className="text-white/70 hover:text-white"
              onClick={() => {
                logout();
                nav("/login");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
