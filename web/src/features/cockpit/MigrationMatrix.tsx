import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { BandPill } from "../../components/ui";
import { cn } from "../../lib/cn";
import { BAND_LABEL } from "../../lib/format";
import { monthLabel } from "../../lib/time";
import type { Migration } from "../../lib/types";

/** How many monitored accounts moved between score bands from last month to this month. */
export function MigrationMatrix({ data }: { data: Migration }) {
  const { bands, matrix } = data;
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-1 text-13">
          <caption className="sr-only">
            Accounts by score band in {monthLabel(data.from_month)} (rows) and {monthLabel(data.to_month)} (columns)
          </caption>
          <thead>
            <tr>
              <th scope="col" className="text-left text-xs font-medium text-fg-muted">
                {monthLabel(data.from_month)} ↓ · {monthLabel(data.to_month)} →
              </th>
              {bands.map((b) => (
                <th key={b} scope="col" className="pb-1 text-center">
                  <BandPill band={b} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {bands.map((from, i) => (
              <tr key={from}>
                <th scope="row" className="pr-2 text-left">
                  <BandPill band={from} />
                </th>
                {bands.map((to, j) => {
                  const n = matrix[from][to];
                  const kind = i === j ? "same" : j > i ? "down" : "up";
                  return (
                    <td
                      key={to}
                      aria-label={`${n} accounts from ${BAND_LABEL[from]} to ${BAND_LABEL[to]}${kind === "same" ? " (unchanged)" : kind === "down" ? " (downgraded)" : " (upgraded)"}`}
                      className={cn(
                        "tabular h-12 rounded-md text-center text-base font-semibold",
                        n === 0 ? "bg-panel-2 text-fg-subtle" : kind === "same" ? "bg-panel-2 text-fg" : kind === "down" ? "bg-danger-tint text-danger" : "bg-success-tint text-success",
                      )}
                    >
                      {n}
                      {n > 0 && kind !== "same" && <span className="ml-1 text-xs font-medium">{kind === "down" ? "↓" : "↑"}</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="tabular mt-2 flex flex-wrap items-center gap-x-4 text-13 text-fg-muted">
        <span>{data.accounts} accounts</span>
        <span className="inline-flex items-center gap-1 text-danger">
          <ArrowDownRight className="h-3.5 w-3.5" aria-hidden />
          {data.downgrades} downgraded
        </span>
        <span className="inline-flex items-center gap-1 text-success">
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          {data.upgrades} upgraded
        </span>
      </p>
      {data.movers.length > 0 && (
        <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto">
          {data.movers.map((m) => (
            <li key={m.factory_id} className="flex items-center gap-2 text-13">
              {m.direction === "down" ? <ArrowDownRight className="h-3.5 w-3.5 shrink-0 text-danger" aria-hidden /> : <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden />}
              <Link to={`/console/${m.application_id}`} className="truncate font-medium text-fg hover:text-primary hover:underline">
                {m.name}
              </Link>
              <span className="tabular ml-auto shrink-0 text-fg-muted">
                {m.from_score} → {m.to_score}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
