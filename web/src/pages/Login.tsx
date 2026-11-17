import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, ChartPie, Clock, LayoutList, RotateCcw, ShieldCheck, Smartphone, type LucideIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button, ErrorNote, Field, Input } from "../components/ui";
import { api, post } from "../lib/api";
import { DEMO_PASSWORD, homeFor, PERSONAS, useAuth } from "../lib/auth";
import { PrototypeBanner } from "../components/shell/PrototypeBanner";

const ICON: Record<string, LucideIcon> = { rm: LayoutList, credit_officer: ShieldCheck, risk: ChartPie, msme: Smartphone };

const PROMISES = [
  {
    title: "Lend on production, not property",
    body: "A Factory Health Score from consented GST, e-way bill, bank, power and payroll signals, with the top reasons in plain language.",
  },
  { title: "The officer decides", body: "AI drafts the credit memo with policy citations. Only a credit officer can approve or reject." },
  { title: "See stress months earlier", body: "Continuous early-warning alerts with a next-best action, before an account turns into a Special Mention Account." },
];

export default function Login() {
  const { login, expired } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const demo = useQuery({ queryKey: ["demo-status"], queryFn: () => api<{ demo_mode: boolean }>("/demo/status"), retry: false, staleTime: Infinity });
  const reset = useMutation({
    mutationFn: () => post<{ took_ms: number; sim_date: string }>("/demo/reset"),
    onSuccess: (r) => toast.success(`Demo data reset in ${(r.took_ms / 1000).toFixed(1)} s. Clock back to ${r.sim_date}.`),
    onError: (e) => toast.error(`Reset failed: ${(e as Error).message}`),
  });

  async function signIn(user: string, pass: string) {
    setBusy(user);
    setError(null);
    try {
      const s = await login(user, pass);
      nav(homeFor(s.role));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (username.trim() && password) void signIn(username.trim(), password);
  }

  return (
    <>
      <PrototypeBanner />
      <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
        <section
          className="hidden flex-col justify-between border-r border-edge bg-panel p-12 lg:flex"
          style={{ backgroundImage: "radial-gradient(60rem 30rem at 0% 0%, color-mix(in srgb, var(--primary) 4%, transparent), transparent)" }}
        >
          <div className="flex items-center gap-2.5">
            <img src="/icon.svg" alt="" className="h-9 w-9 rounded-lg" />
            <span className="text-xl font-semibold tracking-tight text-fg">UdyamPulse</span>
          </div>
          <div className="max-w-lg">
            <h1 className="text-3xl font-semibold tracking-tight text-fg">
              Credit backed by your production, <span className="text-brand">not your property.</span>
            </h1>
            <p className="mt-3 text-base text-fg-muted">Decision intelligence for MSME manufacturing credit.</p>
            <ul className="mt-8 space-y-5">
              {PROMISES.map((p) => (
                <li key={p.title} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden />
                  <div>
                    <p className="text-sm font-semibold text-fg">{p.title}</p>
                    <p className="mt-0.5 text-sm text-fg-muted">{p.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-fg-muted">Prototype · 100% synthetic data · Team Legit, VIT Bhopal University · Visionet Talent Quest 2026</p>
        </section>

        <main className="flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-md">
            <div className="mb-6 flex items-center gap-2.5 lg:hidden">
              <img src="/icon.svg" alt="" className="h-8 w-8 rounded-lg" />
              <span className="text-lg font-semibold text-fg">UdyamPulse</span>
            </div>

            <div className="rounded-card border border-edge bg-panel p-6 shadow-card">
              <h2 className="text-xl font-semibold text-fg">Sign in</h2>
              <p className="mt-1 text-13 text-fg-muted">Use your bank credentials, or pick a demo persona below.</p>

              {expired && (
                <p role="status" className="mt-4 flex items-center gap-2 rounded-control bg-warning-tint px-3 py-2 text-sm text-warning">
                  <Clock className="h-4 w-4 shrink-0" aria-hidden />
                  Your session expired. Please sign in again.
                </p>
              )}

              <form onSubmit={onSubmit} noValidate className="mt-5 space-y-4">
                <Field label="Username" required error={touched && !username.trim() ? "Enter your username" : null}>
                  <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} />
                </Field>
                <Field label="Password" required error={touched && !password ? "Enter your password" : null}>
                  <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
                </Field>
                <ErrorNote error={error} />
                <Button type="submit" variant="primary" className="w-full" loading={busy !== null && busy === username.trim()} disabled={busy !== null}>
                  Sign in
                </Button>
              </form>

              <div className="my-5 flex items-center gap-3 text-xs text-fg-muted">
                <span className="h-px flex-1 bg-edge" />
                One-click demo personas
                <span className="h-px flex-1 bg-edge" />
              </div>

              <ul className="space-y-2">
                {PERSONAS.map((p) => {
                  const Icon = ICON[p.role];
                  return (
                    <li key={p.username}>
                      <button
                        type="button"
                        disabled={busy !== null}
                        onClick={() => signIn(p.username, DEMO_PASSWORD)}
                        aria-label={`Sign in as ${p.title} (${p.username})`}
                        className="group flex w-full items-center gap-3 rounded-control border border-edge bg-panel px-3 py-2.5 text-left transition-colors hover:border-primary hover:bg-primary-tint disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-panel-2 text-fg-muted group-hover:bg-panel group-hover:text-primary">
                          <Icon className="h-[18px] w-[18px]" aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium text-fg">{p.title}</span>
                          <span className="block truncate text-xs text-fg-muted">{busy === p.username ? "Signing in…" : p.desc}</span>
                        </span>
                        <ArrowRight className="h-4 w-4 shrink-0 text-fg-muted group-hover:text-primary" aria-hidden />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            {demo.data?.demo_mode && (
              <p className="mt-4 text-center text-xs text-fg-muted">
                Presenter:{" "}
                <button
                  type="button"
                  onClick={() => reset.mutate()}
                  disabled={reset.isPending}
                  className="inline-flex items-center gap-1 font-medium text-primary underline-offset-2 hover:underline disabled:opacity-60"
                >
                  <RotateCcw className="h-3 w-3" aria-hidden />
                  {reset.isPending ? "Resetting…" : "Reset demo data"}
                </button>
              </p>
            )}
          </div>
        </main>
      </div>
    </>
  );
}
