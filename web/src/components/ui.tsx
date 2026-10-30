import type { ReactNode } from "react";
import { BAND_STYLE, SEVERITY_STYLE } from "../lib/format";

export function AiLabel({ className = "" }: { className?: string }) {
  return (
    <p className={`inline-flex items-center gap-1.5 rounded-full bg-violet/10 px-2.5 py-1 text-[11px] font-medium text-violet ${className}`}>
      <span aria-hidden>✦</span> AI-generated recommendation · final decision by credit officer
    </p>
  );
}

export function BandChip({ band }: { band?: string | null }) {
  if (!band) return <span className="text-muted">–</span>;
  const s = BAND_STYLE[band];
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${s.cls}`}>{s.label}</span>;
}

export function SeverityChip({ severity }: { severity?: string | null }) {
  if (!severity) return null;
  const s = SEVERITY_STYLE[severity];
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-bold uppercase ${s.cls}`}>
      <span aria-hidden>{s.icon}</span>
      {severity}
    </span>
  );
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold text-navy">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p className="rounded-lg bg-magenta/10 px-3 py-2 text-sm text-magenta">{error}</p>;
}

const STEPS = ["APPLIED", "CONSENTED", "SCORED", "MEMO_DRAFTED", "DECIDED", "DISBURSED", "MONITORING"];

export function Stepper({ state }: { state: string }) {
  const idx = STEPS.indexOf(state);
  return (
    <ol className="flex flex-wrap items-center gap-1 text-[11px] font-semibold">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-1">
          <span className={`rounded-full px-2 py-1 ${i < idx ? "bg-green/15 text-green" : i === idx ? "bg-navy text-white" : "bg-line text-muted"}`}>
            {s.replace("_", " ").toLowerCase()}
          </span>
          {i < STEPS.length - 1 && <span className="text-line">→</span>}
        </li>
      ))}
    </ol>
  );
}

export function Kpi({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card p-4">
      <p className="label">{label}</p>
      <p className="mt-1 text-2xl font-bold text-navy tabular-nums">{value}</p>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  );
}
