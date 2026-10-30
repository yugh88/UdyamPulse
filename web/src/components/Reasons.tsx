import { PILLAR_COLORS } from "../lib/format";

export interface Reason {
  feature: string;
  pillar: string;
  text: string;
  points: number;
  direction: "risk_up" | "risk_down";
}
export interface Pillar {
  pillar: string;
  label: string;
  prior_weight: number;
  points: number;
  health: number;
}

export function ReasonList({ reasons }: { reasons: Reason[] }) {
  return (
    <ol className="space-y-2">
      {reasons.map((r, i) => (
        <li key={r.feature} className="flex items-start gap-3 rounded-lg border border-line px-3 py-2">
          <span className="mt-0.5 text-xs font-bold text-muted">{i + 1}</span>
          <span className="flex-1 text-sm">{r.text}</span>
          <span className={`whitespace-nowrap text-sm font-semibold tabular-nums ${r.points >= 0 ? "text-green" : "text-magenta"}`}>
            {r.points >= 0 ? "▲ +" : "▼ "}
            {r.points.toFixed(1)} pts
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Diverging bars: SHAP contribution of each pillar in score points around a zero baseline. */
export function PillarBars({ pillars }: { pillars: Pillar[] }) {
  const max = Math.max(10, ...pillars.map((p) => Math.abs(p.points)));
  return (
    <div className="space-y-2.5">
      {pillars.map((p) => {
        const w = (Math.abs(p.points) / max) * 50;
        return (
          <div key={p.pillar} className="grid grid-cols-[170px_1fr_56px] items-center gap-3 text-sm" title={`${p.label}: ${p.points} points (prior weight ${p.prior_weight * 100}%)`}>
            <span className="flex items-center gap-2 truncate">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: PILLAR_COLORS[p.pillar] }} />
              {p.label}
            </span>
            <div className="relative h-3 rounded bg-surface">
              <div className="absolute inset-y-0 left-1/2 w-px bg-muted/40" />
              <div
                className="absolute inset-y-0.5 rounded"
                style={{
                  width: `${w}%`,
                  left: p.points >= 0 ? "50%" : `${50 - w}%`,
                  background: p.points >= 0 ? "#2FA866" : "#E5397A",
                }}
              />
            </div>
            <span className={`text-right font-semibold tabular-nums ${p.points >= 0 ? "text-green" : "text-magenta"}`}>
              {p.points > 0 ? "+" : ""}
              {p.points.toFixed(1)}
            </span>
          </div>
        );
      })}
      <p className="pt-1 text-[11px] text-muted">Score points contributed by each pillar (SHAP). Prior weights: 25 / 25 / 20 / 15 / 15%.</p>
    </div>
  );
}
