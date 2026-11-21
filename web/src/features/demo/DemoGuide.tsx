import { ArrowLeft, ArrowRight, Compass, Play, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../../components/ui";
import { api, post } from "../../lib/api";
import { DEMO_PASSWORD, ROLE_LABEL, useAuth, type Role } from "../../lib/auth";
import { guide, useGuide } from "./guideStore";

interface Step {
  persona: { username: string; role: Role };
  where: "hero" | "/alerts" | "/msme" | "/governance";
  title: string;
  doThis: string;
  say: string;
}

/** The 5-minute story (docs/DEMO_SCRIPT.md), one persona and one screen per step. */
export const STEPS: Step[] = [
  {
    persona: { username: "rm1", role: "rm" },
    where: "hero",
    title: "Consent and data pull",
    doThis: "Click “Request consent and pull data”. Watch “What changed” gain a consent entry.",
    say: "Consent comes through the Account Aggregator with a stated purpose. GST, e-way bills, bank, power and EPFO data are pulled and cross-checked.",
  },
  {
    persona: { username: "rm1", role: "rm" },
    where: "hero",
    title: "Explainable score",
    doThis: "Click “Run scoring”. The toast shows the new score; the gauge, reasons and timeline update.",
    say: "A Factory Health Score with its top reasons in plain words, and how many points each one adds or removes.",
  },
  {
    persona: { username: "rm1", role: "rm" },
    where: "hero",
    title: "Credit memo with citations",
    doThis: "Click “Generate memo”. “Memo ready” appears in What changed; open a blue policy chip and the agent trace.",
    say: "Every number comes from the scoring and policy engines; the writer only drafts prose, and a guard rejects invented numbers. Policy clauses are cited.",
  },
  {
    persona: { username: "co1", role: "credit_officer" },
    where: "hero",
    title: "Human decision",
    doThis: "Click “Review & decide”, add a comment, confirm the approval, then disburse.",
    say: "Only the credit officer can decide. The stepper moves to Decision ✓, the Key Fact Statement is issued, and the change is on the timeline.",
  },
  {
    persona: { username: "risk1", role: "risk" },
    where: "/alerts",
    title: "Early warning",
    doThis: "Click “Fast-forward 1 week” (or “Play 6 weeks”) until Sharma’s NEW high-risk alert appears, then read before → after.",
    say: "The biggest buyer cut orders. The tiles show e-way bills, power and the score before and after, and the alert suggests a visit and a limit review.",
  },
  {
    persona: { username: "sharma", role: "msme" },
    where: "/msme",
    title: "The owner’s view, in Hindi",
    doThis: "See readiness and the plan, switch to हिं, then Consent → “सहमति वापस लें”.",
    say: "The owner sees the same truth in simple language. Stopping sharing ends pulls immediately and deletes the bank’s copy.",
  },
  {
    persona: { username: "risk1", role: "risk" },
    where: "/governance",
    title: "Governance and honest numbers",
    doThis: "Open Data & models, then Audit trail → Verify chain.",
    say: "Real benchmarks and synthetic results are reported apart, with confidence intervals. Every action is on a tamper-evident audit chain.",
  },
];

type AppRow = { id: number; factory_id: string };

/** The hero's page: in the pipeline before disbursal, in the monitored book after it. */
async function heroPath(): Promise<string> {
  const pipeline = await api<AppRow[]>("/applications");
  const hero = pipeline.find((a) => a.factory_id === "UP-F0001") ?? (await api<AppRow[]>("/applications?state=MONITORING&limit=500")).find((a) => a.factory_id === "UP-F0001");
  return hero ? `/console/${hero.id}` : "/console";
}

export function GuideLauncher({ className }: { className?: string }) {
  return (
    <Button variant="ghost" size="sm" className={className} onClick={() => guide.open()} icon={<Compass className="h-4 w-4" aria-hidden />}>
      Guided demo
    </Button>
  );
}

export function DemoGuide() {
  const { open, step } = useGuide();
  const { session, login, logout } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  if (!open) return null;
  const s = STEPS[Math.min(step, STEPS.length - 1)];
  const here = session?.username === s.persona.username;

  const take = async () => {
    setBusy(true);
    try {
      if (!here) {
        if (session) logout();
        await login(s.persona.username, DEMO_PASSWORD);
      }
      navigate(s.where === "hero" ? await heroPath() : s.where);
    } catch (e) {
      toast.error(`Could not open this step: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      const r = await post<{ took_ms: number }>("/demo/reset");
      toast.success(`Demo reset in ${(r.took_ms / 1000).toFixed(1)} s.`);
      guide.go(0);
      if (session) logout();
      navigate("/login");
    } catch (e) {
      toast.error(`Reset failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside aria-label="Guided demo" className="fixed bottom-4 left-4 z-50 w-[min(24rem,calc(100vw-2rem))] rounded-card border border-edge bg-panel p-5 shadow-pop">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-fg-muted">
            Guided demo · step {step + 1} of {STEPS.length}
          </p>
          <h2 className="mt-0.5 text-base font-semibold text-fg">{s.title}</h2>
        </div>
        <Button variant="ghost" size="sm" aria-label="Close the guided demo" onClick={() => guide.close()} icon={<X className="h-4 w-4" aria-hidden />} />
      </div>
      <p className="mt-2 text-xs text-fg-muted">
        As <span className="font-medium text-fg">{ROLE_LABEL[s.persona.role]}</span> ({s.persona.username})
      </p>
      <p className="mt-2 text-sm text-fg">{s.doThis}</p>
      <p className="mt-2 rounded-control bg-purple-tint p-3 text-sm text-fg">“{s.say}”</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="primary" size="sm" loading={busy} onClick={take} icon={<Play className="h-4 w-4" aria-hidden />}>
          {here ? "Open this screen" : `Sign in as ${s.persona.username} and open`}
        </Button>
        <div className="ml-auto flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            aria-label="Previous step"
            disabled={step === 0}
            onClick={() => guide.go(step - 1)}
            icon={<ArrowLeft className="h-4 w-4" aria-hidden />}
          />
          <Button
            variant="ghost"
            size="sm"
            aria-label="Next step"
            disabled={step >= STEPS.length - 1}
            onClick={() => guide.go(step + 1)}
            icon={<ArrowRight className="h-4 w-4" aria-hidden />}
          />
        </div>
      </div>
      {step === 0 && (
        <Button variant="ghost" size="sm" className="mt-2" loading={busy} onClick={reset} icon={<RotateCcw className="h-4 w-4" aria-hidden />}>
          Reset demo data first
        </Button>
      )}
    </aside>
  );
}
