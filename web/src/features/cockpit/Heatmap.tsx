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

/** Average score → the band palette: brick tint (High risk), ochre tint (Watch), then forest shades that deepen as
 * the score rises. The number is always printed in the cell, so colour is never the only signal. */
function scoreFill(score: number): string {
  if (score < 550) return "var(--danger-tint)";
  if (score < 650) return "var(--warning-tint)";
  const t = Math.min(1, (score - 650) / 150);
  return `color-mix(in srgb, var(--primary) ${Math.round(12 + t * 22)}%, var(--surface))`;
}

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
      {/* Phones: the grid keeps a readable width and scrolls sideways, so no sector name is squeezed or cut. */}
      <p className="mb-1 text-xs text-fg-muted sm:hidden">Swipe sideways to see every sector →</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-separate border-spacing-1 text-13">
          <caption className="sr-only">
            {metric === "score" ? "Average Factory Health Score" : "Open alerts per account"} by cluster and sector. Select a cell to filter the tables below.
          </caption>
          <thead>
            <tr>
              <td />
              {sectors.map((s) => (
                <th key={s} scope="col" className="px-1 pb-1 text-center text-xs font-medium whitespace-nowrap text-fg-muted">
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
                      <td key={s} className="rounded-md bg-panel-2 text-center text-xs text-fg-muted" aria-label={`${cl}, ${s}: no accounts`}>
                        –
                      </td>
                    );
                  const density = c.alerts / c.accounts;
                  const t = density / maxDensity;
                  const isSel = selected?.cluster === cl && selected.sector === s;
                  return (
                    <td key={s} className="p-0">
                      <button
                        type="button"
                        aria-pressed={isSel}
                        onClick={() => onSelect(isSel ? null : { cluster: cl, sector: s })}
                        aria-label={`${cl}, ${s}: average score ${c.avg_score}, ${c.accounts} accounts, ${c.alerts} open alerts`}
                        className={cn(
                          "tabular flex h-12 w-full min-w-16 flex-col items-center justify-center rounded-md text-fg transition-shadow hover:shadow-pop",
                          isSel && "outline-2 outline-primary",
                        )}
                        style={{ background: metric === "score" ? scoreFill(c.avg_score) : wash("var(--warning)", t) }}
                      >
                        <span className="text-sm font-semibold">{metric === "score" ? c.avg_score : c.alerts ? `${c.alerts} / ${c.accounts}` : "0"}</span>
                        <span className="text-xs text-fg">{metric === "score" ? `${c.accounts} acct${c.accounts === 1 ? "" : "s"}` : "alerts / accts"}</span>
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {metric === "score" ? (
        <ul className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-13 text-fg-muted">
          <li className="inline-flex items-center gap-1.5">
            <span className="h-3 w-5 rounded-sm bg-danger-tint ring-1 ring-edge" aria-hidden />
            below 550 (High risk)
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-3 w-5 rounded-sm bg-warning-tint ring-1 ring-edge" aria-hidden />
            550–649 (Watch)
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-3 w-5 rounded-sm ring-1 ring-edge" style={{ background: scoreFill(700) }} aria-hidden />
            650+ (Approve), deeper green = higher
          </li>
          <li>Every cell shows its number.</li>
        </ul>
      ) : (
        <p className="mt-3 text-13 text-fg-muted">Stronger shading means more open alerts per account. Every cell shows its number.</p>
      )}
    </div>
  );
}
