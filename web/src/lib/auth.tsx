import { createContext, useContext, useState, type ReactNode } from "react";
import { post } from "./api";

export type Role = "rm" | "credit_officer" | "risk" | "msme";
export interface Session {
  username: string;
  role: Role;
  display_name: string;
  factory_id: string | null;
}

interface AuthCtx {
  session: Session | null;
  login: (username: string, password: string) => Promise<Session>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const raw = localStorage.getItem("up_session");
    return raw ? (JSON.parse(raw) as Session) : null;
  });

  async function login(username: string, password: string) {
    const r = await post<{ access_token: string; role: Role; display_name: string; factory_id: string | null }>(
      "/auth/login",
      { username, password },
    );
    const s: Session = { username, role: r.role, display_name: r.display_name, factory_id: r.factory_id };
    localStorage.setItem("up_token", r.access_token);
    localStorage.setItem("up_session", JSON.stringify(s));
    setSession(s);
    return s;
  }

  function logout() {
    localStorage.removeItem("up_token");
    localStorage.removeItem("up_session");
    setSession(null);
  }

  return <Ctx.Provider value={{ session, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}

export function homeFor(role: Role): string {
  return { rm: "/console", credit_officer: "/console", risk: "/cockpit", msme: "/msme" }[role];
}
