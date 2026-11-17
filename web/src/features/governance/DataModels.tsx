import { useQuery } from "@tanstack/react-query";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, ChartFrame, GRID, TOOLTIP } from "../../components/charts";
import { ProvenanceBadge } from "../../components/provenance";
import { Badge, Card, ErrorState, Skeleton, Stat } from "../../components/ui";
import { api } from "../../lib/api";
import { dateTime } from "../../lib/time";

type CI = [number, number] | null;
interface Metric {
  n: number;
  positives: number;
  event_rate: number;
  factories?: number;
  auc: number;
  auc_ci95: CI;
  ks?: number;
  ks_ci95?: CI;
  brier?: number;
  brier_ci95?: CI;
}
interface GroupMetric extends Metric {
  group: string;
}
interface CalRow {
  bin: number;
  n: number;
  mean_predicted: number;
  observed: number;
}
interface EwsPoint {
  min_points: number;
  recall: number;
  median_lead_days: number | null;
  precision_sma2_within_6m: number | null;
  alerted_accounts: number;
}
interface DataModels {
  dataset_in_use: { name: string; factories: number; months: number };
  provenance: {
    dataset: string;
    provenance: string;
    source: string;
    licence: string;
    rows: number | null;
    unit: string;
    date_range: string;
    retrieved_at: string | null;
    used_for: string;
  }[];
  product_model: {
    provenance: string;
    dataset: string;
    test: Metric;
    fold_auc_mean: number;
    fold_auc_sd: number;
    expected_calibration_error: number;
    calibration: CalRow[];
    operating_point: { rule: string; precision: number; recall: number; flag_rate: number };
    sector_holdout: GroupMetric[];
    cluster_holdout: GroupMetric[];
    shock: GroupMetric[];
    ablation: { with_production_signals_auc: number; without_production_signals_auc: number; uplift_auc: number; uplift_ci95: [number, number]; caveat: string };
    leakage_audit: {
      passed: boolean;
      factory_months_checked: number;
      shuffled_label_auc: number;
      shuffled_label_runs: number[];
      shuffled_label_passed: boolean;
      domain_prior_auc: number;
    };
    ews: { chosen: EwsPoint | null; rule: string; operating_points: EwsPoint[] };
  } | null;
  demo_model: { test: { auc: number; positives: number; n: number } } | null;
  real_benchmarks: { key: string; dataset: string; provenance: string; purpose: string; licence: string; label: string | null; test: Metric; state_holdout: Metric | null }[];
  benchmark_caption: string;
}

// Reports can come from an older run: a missing number shows as "n/a" instead of breaking the tab.
const f3 = (x: number | null | undefined) => (typeof x === "number" ? x.toFixed(3) : "n/a");
const ci = (c: CI | undefined) => (c ? `${f3(c[0])}–${f3(c[1])}` : "n/a");
const pct = (x: number | null | undefined, d = 1) => (typeof x === "number" ? `${(x * 100).toFixed(d)}%` : "n/a");

/** Point estimate with its 95% interval, on one shared 0.5–1.0 AUC scale (0.5 = coin toss). */
function ForestTable({ caption, rows }: { caption: string; rows: GroupMetric[] }) {
  const lo = 0.5;
  const x = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / (1 - lo)) * 100))}%`;
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="text-left text-xs text-fg-muted">
          <th className="py-1.5 pr-3 font-medium">Held out</th>
          <th className="w-full py-1.5 pr-3 font-medium">
            AUC with 95% CI <span className="font-normal">(scale 0.5 to 1.0)</span>
          </th>
          <th className="py-1.5 pr-3 text-right font-medium">AUC</th>
          <th className="py-1.5 text-right font-medium whitespace-nowrap">Defaults</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.group} className="border-t border-edge" title={`${r.group}: AUC ${f3(r.auc)} (95% CI ${ci(r.auc_ci95)}), ${r.n.toLocaleString("en-IN")} rows`}>
            <th scope="row" className="py-2 pr-3 text-left font-normal whitespace-nowrap">
              {r.group.replace(/_/g, " ")}
            </th>
            <td className="py-2 pr-3" aria-hidden>
              <div className="relative h-4">
                <div className="absolute top-1/2 h-px w-full bg-edge" />
                {r.auc_ci95 && (
                  <div
                    className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-[var(--chart-1)] opacity-40"
                    style={{ left: x(r.auc_ci95[0]), width: `calc(${x(r.auc_ci95[1])} - ${x(r.auc_ci95[0])})` }}
                  />
                )}
                <div
                  className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--surface)] bg-[var(--chart-1)]"
                  style={{ left: x(r.auc) }}
                />
              </div>
            </td>
            <td className="tabular py-2 pr-3 text-right whitespace-nowrap">
              {f3(r.auc)} <span className="text-xs text-fg-muted">({ci(r.auc_ci95)})</span>
            </td>
            <td className="tabular py-2 text-right">{r.positives.toLocaleString("en-IN")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CalibrationPlot({ rows }: { rows: CalRow[] }) {
  const max = Math.max(...rows.map((r) => Math.max(r.mean_predicted, r.observed)), 0.01) * 1.08;
  const data = rows.map((r) => ({ ...r, predicted: r.mean_predicted }));
  return (
    <>
      <ChartFrame
        label={`Calibration: predicted versus observed default rate across ${rows.length} score deciles. Points close to the diagonal mean predictions match reality.`}
        height={240}
      >
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid {...GRID} vertical />
            <XAxis
              type="number"
              dataKey="predicted"
              domain={[0, max]}
              tickFormatter={(v) => pct(v, 0)}
              {...AXIS}
              label={{ value: "Predicted PD", position: "insideBottom", offset: -2, fontSize: 11, fill: "var(--text-muted)" }}
              height={36}
            />
            <YAxis type="number" domain={[0, max]} tickFormatter={(v) => pct(v, 0)} {...AXIS} width={44} />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: max, y: max },
              ]}
              stroke="var(--border-strong)"
              strokeDasharray="4 4"
            />
            <Tooltip {...TOOLTIP} formatter={(v: number) => pct(v, 2)} labelFormatter={(v: number) => `Predicted ${pct(v, 2)}`} />
            <Line
              type="linear"
              dataKey="observed"
              name="Observed default rate"
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
              activeDot={{ r: 6 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
      <p className="mt-1 text-xs text-fg-muted">Dashed line: perfect calibration. Each point is one score decile of the out-of-time test.</p>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-fg-muted">Show as a table</summary>
        <table className="tabular mt-2 w-full">
          <thead>
            <tr className="text-left text-fg-muted">
              <th className="py-1 font-medium">Decile</th>
              <th className="py-1 text-right font-medium">Rows</th>
              <th className="py-1 text-right font-medium">Predicted</th>
              <th className="py-1 text-right font-medium">Observed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.bin} className="border-t border-edge">
                <td className="py-1">{r.bin}</td>
                <td className="py-1 text-right">{r.n.toLocaleString("en-IN")}</td>
                <td className="py-1 text-right">{pct(r.mean_predicted, 2)}</td>
                <td className="py-1 text-right">{pct(r.observed, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

function Check({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      {ok ? (
        <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-label="passed" />
      ) : (
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-label="failed" />
      )}
      <span>{children}</span>
    </li>
  );
}

export function DataModelsTab() {
  const q = useQuery({ queryKey: ["data-models"], queryFn: () => api<DataModels>("/data-models") });
  if (q.isLoading) return <Skeleton className="h-96" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data!;
  const pm = d.product_model;
  return (
    <div className="grid gap-4">
      <Card
        title="Data provenance"
        description="Every dataset behind the scores, what is real and what is synthetic. Real and synthetic results are reported separately, never blended."
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-left text-xs text-fg-muted">
                {["Dataset", "Provenance", "Source and licence", "Rows", "Range", "Retrieved", "Used for"].map((h) => (
                  <th key={h} className="py-2 pr-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.provenance.map((p) => (
                <tr key={p.dataset} className="border-t border-edge align-top">
                  <td className="py-2 pr-3 font-medium">{p.dataset}</td>
                  <td className="py-2 pr-3">
                    <ProvenanceBadge value={p.provenance} />
                  </td>
                  <td className="py-2 pr-3 text-fg-muted">
                    {p.source}
                    <br />
                    <span className="text-xs">{p.licence}</span>
                  </td>
                  <td className="tabular py-2 pr-3 whitespace-nowrap">{p.rows != null ? `${p.rows.toLocaleString("en-IN")} ${p.unit}` : "–"}</td>
                  <td className="py-2 pr-3 text-fg-muted">{p.date_range}</td>
                  <td className="py-2 pr-3 whitespace-nowrap text-fg-muted">{p.retrieved_at ? dateTime(p.retrieved_at) : "–"}</td>
                  <td className="py-2 text-fg-muted">{p.used_for}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-fg-muted">
          Dataset in use by this server: <span className="font-medium text-fg">{d.dataset_in_use.name}</span> ({d.dataset_in_use.factories.toLocaleString("en-IN")} factories ×{" "}
          {d.dataset_in_use.months} months).
        </p>
      </Card>

      {pm && (
        <Card title="Product model" description={pm.dataset} actions={<ProvenanceBadge value={pm.provenance} />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="AUC, out of time and out of group" value={f3(pm.test.auc)} sub={`95% CI ${ci(pm.test.auc_ci95)}`} />
            <Stat label="KS" value={f3(pm.test.ks ?? 0)} sub={`95% CI ${ci(pm.test.ks_ci95)}`} />
            <Stat label="Brier score (calibrated)" value={(pm.test.brier ?? 0).toFixed(4)} sub={`ECE ${pm.expected_calibration_error.toFixed(4)}`} />
            <Stat
              label="Test defaults"
              value={pm.test.positives.toLocaleString("en-IN")}
              sub={`${(pm.test.factories ?? 0).toLocaleString("en-IN")} factories, ${pct(pm.test.event_rate, 2)} rate`}
            />
          </div>
          <p className="mt-3 text-sm text-fg-muted">
            Confidence intervals resample whole factories (1,000 times). AUC across the five factory groups: {f3(pm.fold_auc_mean)} ± {f3(pm.fold_auc_sd)}. At the{" "}
            {pm.operating_point.rule.toLowerCase()}: precision {pct(pm.operating_point.precision)}, recall {pct(pm.operating_point.recall)}, {pct(pm.operating_point.flag_rate)} of
            account-months flagged.
            {d.demo_model && ` The live walkthrough uses a smaller demo model (test AUC ${f3(d.demo_model.test.auc)} on ${d.demo_model.test.positives} defaults).`}
          </p>
          <div className="mt-5 grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold">Unseen sectors and clusters</h3>
              <ForestTable caption="AUC when a whole sector is held out of training" rows={pm.sector_holdout} />
              <div className="mt-4">
                <ForestTable caption="AUC when a whole cluster is held out of training" rows={pm.cluster_holdout} />
              </div>
              <h3 className="mt-5 mb-2 text-sm font-semibold">Across the macro shock (trained before it)</h3>
              <ForestTable caption="AUC before, during and after the macro shock" rows={pm.shock} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">Calibration</h3>
              <CalibrationPlot rows={pm.calibration} />
              <h3 className="mt-5 mb-2 text-sm font-semibold">Checks</h3>
              <ul className="grid gap-2">
                <Check ok={pm.leakage_audit.passed}>
                  No look-ahead: features recomputed from history cut at the scoring month match for {pm.leakage_audit.factory_months_checked} factory-months.
                </Check>
                <Check ok={pm.leakage_audit.shuffled_label_passed}>
                  Shuffled labels, 8 runs: mean AUC {f3(pm.leakage_audit.shuffled_label_auc)}, scattered around a coin toss in both directions, as it should be without leakage.
                </Check>
                <li className="text-xs text-fg-muted">
                  With monotone constraints the same shuffled labels still give AUC {f3(pm.leakage_audit.domain_prior_auc)}: the economic directions alone carry real signal, like
                  an expert scorecard.
                </li>
              </ul>
              <h3 className="mt-5 mb-2 text-sm font-semibold">Ablation: production signals</h3>
              <p className="text-sm">
                AUC {f3(pm.ablation.with_production_signals_auc)} with e-way bill, power and purchase-order signals, {f3(pm.ablation.without_production_signals_auc)} without:
                uplift {pm.ablation.uplift_auc >= 0 ? "+" : ""}
                {f3(pm.ablation.uplift_auc)} (95% CI {ci(pm.ablation.uplift_ci95)}).
              </p>
              <p className="mt-1 text-xs text-warning">{pm.ablation.caveat}</p>
              {pm.ews.chosen && (
                <>
                  <h3 className="mt-5 mb-2 text-sm font-semibold">Early-warning operating point</h3>
                  <p className="text-sm">
                    Alerts at {pm.ews.chosen.min_points}+ points: recall {pct(pm.ews.chosen.recall)}, median lead {pm.ews.chosen.median_lead_days} days, precision{" "}
                    {pct(pm.ews.chosen.precision_sma2_within_6m ?? 0)} ({pm.ews.rule}).
                  </p>
                </>
              )}
            </div>
          </div>
        </Card>
      )}

      {d.real_benchmarks.length > 0 && (
        <Card title="Real-world benchmark" description={d.benchmark_caption} actions={<ProvenanceBadge value="Real public data" />}>
          <div className="grid gap-4 md:grid-cols-2">
            {d.real_benchmarks.map((b) => (
              <div key={b.key} className="rounded-lg border border-edge p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold">{b.dataset}</h3>
                  <Badge tone="neutral">{b.licence}</Badge>
                </div>
                <p className="mt-1 text-xs text-fg-muted">{b.purpose}</p>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <Stat label="Test AUC" value={f3(b.test.auc)} sub={`95% CI ${ci(b.test.auc_ci95)}`} />
                  <Stat label="KS" value={f3(b.test.ks ?? 0)} sub={`CI ${ci(b.test.ks_ci95)}`} />
                  <Stat label="Defaults" value={b.test.positives.toLocaleString("en-IN")} sub={`of ${b.test.n.toLocaleString("en-IN")}`} />
                </div>
                {b.state_holdout && (
                  <p className="mt-2 text-xs text-fg-muted">
                    Unseen U.S. states: AUC {f3(b.state_holdout.auc)} (95% CI {ci(b.state_holdout.auc_ci95)}).
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
