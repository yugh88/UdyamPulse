import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { post, setAccessToken, UNAUTHORIZED_EVENT } from "./api";

export type Role = "rm" | "credit_officer" | "risk" | "msme";
export interface Session {
  username: string;
  role: Role;
  display_name: string;
  factory_id: string | null;
  tenant_name: string;
}

export const ROLE_LABEL: Record<Role, string> = { rm: "Relationship Manager", credit_officer: "Credit Officer", risk: "Risk Head", msme: "MSME Owner" };

/** Demo personas (synthetic users seeded by `api/seed.py`; every password is `demo123`). */
export const PERSONAS: { username: string; role: Role; title: string; desc: string }[] = [
  { username: "rm1", role: "rm", title: "Relationship Manager", desc: "Open applications, take consent, score, draft memos, act on alerts." },
  { username: "co1", role: "credit_officer", title: "Credit Officer", desc: "Review the memo and approve or reject. The only role that can decide." },
  { username: "risk1", role: "risk", title: "Risk Head", desc: "Early-warning alerts, portfolio, model card, fairness and drift, full audit trail." },
  { username: "sharma", role: "msme", title: "MSME Owner", desc: "Sharma Auto Components: readiness, cash-flow forecast, 90-day plan, consent." },
];
export const DEMO_PASSWORD = "demo123";

interface AuthCtx {
  session: Session | null;
  /** True when the last sign-out was forced by an expired session. */
  expired: boolean;
  login: (username: string, password: string) => Promise<Session>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

/** Who is signed in (names and role only). No token is ever written to storage: the access token lives in
 * memory and the refresh token is an httpOnly cookie, so a reload renews the session through the cookie. */
function stored(): Session | null {
  try {
    localStorage.removeItem("up_token"); // tokens from older builds
    const raw = localStorage.getItem("up_session");
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [session, setSession] = useState<Session | null>(stored);
  const [expired, setExpired] = useState(false);

  const clear = useCallback(() => {
    setAccessToken(null);
    localStorage.removeItem("up_session");
    qc.clear();
    setSession(null);
  }, [qc]);

  const login = useCallback(
    async (username: string, password: string) => {
      const r = await post<{ access_token: string; role: Role; display_name: string; factory_id: string | null; tenant_name: string }>("/auth/login", { username, password });
      const s: Session = { username, role: r.role, display_name: r.display_name, factory_id: r.factory_id, tenant_name: r.tenant_name };
      qc.clear(); // never show one persona's cached data to the next
      setAccessToken(r.access_token);
      localStorage.setItem("up_session", JSON.stringify(s));
      setExpired(false);
      setSession(s);
      return s;
    },
    [qc],
  );

  const logout = useCallback(() => {
    setExpired(false);
    // Revoke the refresh token on the server; sign-out in this tab does not wait for it.
    post("/auth/logout").catch(() => undefined);
    clear();
  }, [clear]);

  useEffect(() => {
    const onUnauthorized = () => {
      setExpired(true);
      clear();
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [clear]);

  return <Ctx.Provider value={{ session, expired, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}

export function homeFor(role: Role): string {
  return { rm: "/console", credit_officer: "/console", risk: "/alerts", msme: "/msme" }[role];
}
