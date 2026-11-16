import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FlaskConical, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, BandPill, Button, Card, ErrorState, Skeleton } from "../../components/ui";
import { api, post } from "../../lib/api";
import { cn } from "../../lib/cn";
import { pct, signed } from "../../lib/format";
import { monthLabel } from "../../lib/time";
import type { Lever, Simulation } from "../../lib/types";
import { ReasonCards } from "./Score";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const show = (lv: Lever, v: number) => (lv.unit === "%" ? `${signed(v)}%` : lv.unit === "pp" ? `${signed(v)} pts` : lv.unit === "days" ? `${signed(v)} days` : `+${v}`);

/** Sliders change a few signals over the latest months; the model re-scores. Nothing is saved. */
export function WhatIf({ applicationId }: { applicationId: number }) {
  const levers = useQuery({ queryKey: ["levers"], queryFn: () => api<{ window_months: number; levers: Lever[] }>("/score/levers"), staleTime: Infinity });
  const [values, setValues] = useState<Record<string, number>>({});
  const adjustments = useDebounced(values, 250);
  const sim = useQuery({
    queryKey: ["simulate", applicationId, adjustments],
    queryFn: () => post<Simulation>("/score/simulate", { application_id: applicationId, adjustments }),
    placeholderData: (prev) => prev,
  });
  const changed = Object.values(values).some((v) => v !== 0);

  if (levers.isError) return <ErrorState error={levers.error} onRetry={() => levers.refetch()} />;
  const s = sim.data;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      <Card
        title="Change the signals"
        description={levers.data ? `Applied to the latest ${levers.data.window_months} months of data.` : undefined}
        actions={
          <Button size="sm" variant="ghost" disabled={!changed} onClick={() => setValues({})} icon={<RotateCcw className="h-3.5 w-3.5" aria-hidden />}>
            Reset
          </Button>
        }
      >
        {!levers.data ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <ul className="space-y-5">
            {levers.data.levers.map((lv) => {
              const v = values[lv.key] ?? 0;
              return (
                <li key={lv.key}>
                  <div className="flex items-baseline justify-between gap-3">
                    <label htmlFor={`lever-${lv.key}`} className="text-13 font-medium text-fg">
                      {lv.label}
                    </label>
                    <output htmlFor={`lever-${lv.key}`} className={cn("tabular text-13 font-semibold", v === 0 ? "text-fg-muted" : "text-primary")}>
                      {v === 0 ? "no change" : show(lv, v)}
                    </output>
                  </div>
                  <input
                    id={`lever-${lv.key}`}
                    type="range"
                    min={lv.min}
                    max={lv.max}
                    step={lv.step}
                    value={v}
                    onChange={(e) => setValues((prev) => ({ ...prev, [lv.key]: Number(e.target.value) }))}
                    aria-valuetext={v === 0 ? "no change" : show(lv, v)}
                    className="mt-2 w-full accent-[var(--primary)]"
                  />
                  <p className="text-xs text-fg-muted">{lv.help}</p>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card
        title="Simulated result"
        actions={
          <Badge tone="info" icon={<FlaskConical className="h-3.5 w-3.5" aria-hidden />}>
            Simulation
          </Badge>
        }
      >
        {sim.isError ? (
          <ErrorState error={sim.error} onRetry={() => sim.refetch()} />
        ) : !s ? (
          <Skeleton className="h-40" />
        ) : (
          <div aria-live="polite" className={cn("transition-opacity", sim.isFetching && "opacity-60")}>
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <p className="text-xs text-fg-muted">Current · {monthLabel(s.as_of)}</p>
                <p className="tabular text-2xl font-semibold text-fg">{s.base.score}</p>
                <BandPill band={s.base.band} />
              </div>
              <ArrowRight className="h-5 w-5 text-fg-subtle" aria-hidden />
              <div>
                <p className="text-xs text-fg-muted">Simulated</p>
                <p className="tabular text-2xl font-semibold text-fg" data-testid="sim-score">
                  {s.simulated.score}
                </p>
                <BandPill band={s.simulated.band} />
              </div>
              <div className="ml-auto text-right">
                <p className="text-xs text-fg-muted">Change</p>
                <p className={cn("tabular text-2xl font-semibold", s.delta > 0 ? "text-success" : s.delta < 0 ? "text-danger" : "text-fg-muted")}>{signed(s.delta)}</p>
                <p className="tabular text-xs text-fg-muted">
                  PD {pct(s.base.pd_12m, 2)} → {pct(s.simulated.pd_12m, 2)}
                </p>
              </div>
            </div>
            <p className="mt-4 rounded-control bg-info-tint px-3 py-2 text-xs text-info">
              {s.label}. The model is re-run on adjusted data; the application's real score does not change.
            </p>
            <h3 className="mt-5 mb-2 text-13 font-semibold text-fg">Top reasons in this scenario</h3>
            <ReasonCards reasons={s.simulated.reasons} />
          </div>
        )}
      </Card>
    </div>
  );
}
