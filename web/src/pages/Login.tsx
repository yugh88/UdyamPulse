import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNote } from "../components/ui";
import { homeFor, useAuth } from "../lib/auth";

const PERSONAS = [
  { username: "rm1", title: "Relationship Manager", desc: "Open applications, take consent, score, draft memos, act on alerts." },
  { username: "co1", title: "Credit Officer", desc: "Review the memo and approve or reject — the only role that can decide." },
  { username: "risk1", title: "Risk", desc: "Portfolio cockpit, model card, fairness & drift, full audit trail." },
  { username: "sharma", title: "MSME · Sharma Auto Components", desc: "Loan readiness, cash-flow forecast, 90-day plan, consent control." },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function go(username: string) {
    setBusy(username);
    setError(null);
    try {
      const s = await login(username, "demo123");
      nav(homeFor(s.role));
    } catch (e) {
      setError(`Login failed: ${(e as Error).message}. Is the API running on :8000?`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy px-4">
      <div className="w-full max-w-3xl">
        <div className="mb-8 text-center text-white">
          <img src="/icon.svg" alt="" className="mx-auto mb-3 h-14 w-14" />
          <h1 className="text-3xl font-bold">UdyamPulse</h1>
          <p className="mt-2 text-white/70">Credit backed by your production, not your property.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {PERSONAS.map((p) => (
            <button
              key={p.username}
              onClick={() => go(p.username)}
              disabled={busy !== null}
              className="rounded-xl bg-white p-5 text-left shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl disabled:opacity-60"
            >
              <p className="font-semibold text-navy">{p.title}</p>
              <p className="mt-1 text-sm text-muted">{p.desc}</p>
              <p className="mt-3 text-xs font-mono text-violet">{busy === p.username ? "signing in…" : `${p.username} / demo123`}</p>
            </button>
          ))}
        </div>
        <div className="mt-4">
          <ErrorNote error={error} />
        </div>
        <p className="mt-6 text-center text-xs text-white/50">Prototype · synthetic data only · Team Legit, VIT Bhopal · Visionet Talent Quest 2026</p>
      </div>
    </div>
  );
}
