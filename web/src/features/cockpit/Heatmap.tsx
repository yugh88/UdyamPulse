import { useMemo, useState } from "react";
import { cn } from "../../lib/cn";
import type { Portfolio } from "../../lib/types";

type Metric = "score" | "alerts";
export interface CellFilter {
  cluster: string;
  sector: string;
}

/** 0..1 intensity → a wash of the metric colour over the card surface. Text stays the normal foreground. */
const wash = (color: string, t: number) => `color-mix(in srgb, ${color} ${Math.round(8 + t * 42)}%, var(--surface))`;

export function Heatmap({ cells, selected, onSelect }: { cells: Portfolio["heatmap"]; selected: CellFilter | null; onSelect: (c: CellFilter | null) => void }) {
  const [metric, setMetric] = useState<Metric>("score");
  const clusters = useMemo(() => [...new Set(cells.map((c) => c.cluster))].sort(), [cells]);
  const sectors = useMemo(() => [...new Set(cells.map((c) => c.sector))].sort(), [cells]);
  const byKey = useMemo(() => new Map(cells.map((c) => [`${c.cluster}|${c.sector}`, c])), [cells]);
  const maxDensity = Math.max(0.01, ...cells.map((c) => c.alerts / c.accounts));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div role="radiogroup" aria-label="Heat-map metric" className="flex gap-1 rounded-control bg-panel-2 p-1">
          {(
            [
              ["score", "Average score"],
              ["alerts", "Alert density"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={metric === k}
              onClick={() => setMetric(k)}
              className={cn("rounded-md px-2.5 py-1 text-13 font-medium", metric === k ? "bg-panel text-fg shadow-card" : "text-fg-muted hover:text-fg")}
            >
              {label}
            </button>
          ))}
        </div>
        {selected && (
          <button type="button" onClick={() => onSelect(null)} className="text-13 font-medium text-primary hover:underline">
            Clear filter: {selected.cluster} · {selected.sector}
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-1 text-13">
          <caption className="sr-only">{metric === "score" ? "Average Factory Health Score" : "Open alerts per account"} by cluster and sector. Select a cell to filter the tables below.</caption>
          <thead>
            <tr>
              <td />
              {sectors.map((s) => (
                <th key={s} scope="col" className="px-1 pb-1 text-center text-xs font-medium text-fg-muted">
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {clusters.map((cl) => (
              <tr key={cl}>
                <th scope="row" className="pr-2 text-left text-xs font-medium whitespace-nowrap text-fg-muted">
                  {cl}
                </th>
                {sectors.map((s) => {
                  const c = byKey.get(`${cl}|${s}`);
                  if (!c)
                    return (
                      <td key={s} className="rounded-md bg-panel-2 text-center text-xs text-fg-subtle" aria-label={`${cl}, ${s}: no accounts`}>
                        –
                      </td>
                    );
                  const density = c.alerts / c.accounts;
                  const t = metric === "score" ? Math.min(1, Math.max(0, (780 - c.avg_score) / 180)) : density / maxDensity;
                  const isSel = selected?.cluster === cl && selected.sector === s;
                  return (
                    <td key={s} className="p-0">
                      <button
                        type="button"
                        aria-pressed={isSel}
                        onClick={() => onSelect(isSel ? null : { cluster: cl, sector: s })}
                        aria-label={`${cl}, ${s}: average score ${c.avg_score}, ${c.accounts} accounts, ${c.alerts} open alerts`}
                        className={cn("tabular flex h-12 w-full min-w-16 flex-col items-center justify-center rounded-md text-fg transition-shadow hover:shadow-pop", isSel && "outline-2 outline-primary")}
                        style={{ background: wash(metric === "score" ? "var(--danger)" : "var(--warning)", t) }}
                      >
                        <span className="text-sm font-semibold">{metric === "score" ? c.avg_score : c.alerts ? `${c.alerts} / ${c.accounts}` : "0"}</span>
                        <span className="text-[11px] text-fg-muted">{metric === "score" ? `${c.accounts} acct${c.accounts === 1 ? "" : "s"}` : "alerts / accts"}</span>
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-fg-muted">{metric === "score" ? "Stronger shading means a lower average score." : "Stronger shading means more open alerts per account."} Every cell shows its number.</p>
    </div>
  );
}
