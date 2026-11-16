import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, CHART, ChartFrame, GRID, LEGEND, TOOLTIP, X_AXIS } from "../../components/charts";
import { BandPill, EmptyState, SeverityPill, Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui";
import { BAND_VAR, type Band, type Severity } from "../../lib/format";
import { monthLabel } from "../../lib/time";
import type { SignalPoint } from "../../lib/types";

type Unit = "lakh" | "kwh" | "days" | "pct" | "count";
interface Series {
  key: keyof SignalPoint;
  label: string;
  unit: Unit;
  kind?: "line" | "bar";
  axis?: "left" | "right";
}
const TABS: { key: string; label: string; series: Series[] }[] = [
  {
    key: "orders",
    label: "Orders and dispatch",
    series: [
      { key: "eway_value", label: "E-way bill value", unit: "lakh" },
      { key: "einvoice_value", label: "E-invoice value", unit: "lakh" },
      { key: "open_po_value", label: "Open purchase orders", unit: "lakh" },
    ],
  },
  {
    key: "cash",
    label: "Cash flow",
    series: [
      { key: "aa_credits", label: "Bank inflows", unit: "lakh" },
      { key: "aa_debits", label: "Bank outflows", unit: "lakh" },
      { key: "avg_balance", label: "Average balance", unit: "lakh" },
      { key: "bounces", label: "Cheque/NACH bounces", unit: "count", kind: "bar", axis: "right" },
    ],
  },
  {
    key: "production",
    label: "Production (kWh)",
    series: [
      { key: "kwh", label: "Electricity use", unit: "kwh" },
      { key: "epfo_headcount", label: "EPFO headcount", unit: "count", axis: "right" },
    ],
  },
  {
    key: "receivables",
    label: "Receivables",
    series: [
      { key: "avg_days_to_pay", label: "Days buyers take to pay", unit: "days" },
      { key: "top_buyer_share", label: "Top-buyer share of sales", unit: "pct", axis: "right" },
    ],
  },
  {
    key: "compliance",
    label: "Compliance",
    series: [
      { key: "gst_filing_delay_days", label: "GSTR-3B filing delay", unit: "days", kind: "bar" },
      { key: "gst_bank_mismatch", label: "GST vs bank gap", unit: "pct", axis: "right" },
    ],
  },
];

const scale = (v: number, u: Unit) => (u === "lakh" ? v / 1e5 : u === "pct" ? v * 100 : v);
function fmt(v: number, u: Unit): string {
  if (u === "lakh") return `₹${v.toFixed(1)} L`;
  if (u === "pct") return `${v.toFixed(0)}%`;
  if (u === "days") return `${v.toFixed(0)} days`;
  if (u === "kwh") return `${Math.round(v).toLocaleString("en-IN")} kWh`;
  return `${Math.round(v)}`;
}
const tick = (u: Unit) => (v: number) => (u === "lakh" ? `${Math.round(v)}L` : u === "pct" ? `${Math.round(v)}%` : u === "kwh" ? `${Math.round(v / 1000)}k` : `${Math.round(v)}`);

/** Consecutive months in the same score band, drawn as a faint background wash. */
function bandRuns(history: { month: string; band: Band }[]): { from: string; to: string; band: Band }[] {
  const runs: { from: string; to: string; band: Band }[] = [];
  for (const h of history) {
    const last = runs[runs.length - 1];
    if (last && last.band === h.band) last.to = h.month;
    else runs.push({ from: h.month, to: h.month, band: h.band });
  }
  return runs;
}

export function SignalExplorer({
  signals,
  scoreHistory,
  stressStart,
}: {
  signals: SignalPoint[];
  scoreHistory: { month: string; score: number; band: Band }[];
  stressStart: { month: string; severity: Severity } | null;
}) {
  const [tab, setTab] = useState(TABS[0].key);
  const active = TABS.find((t) => t.key === tab)!;
  const left = active.series.find((s) => (s.axis ?? "left") === "left")!;
  const right = active.series.find((s) => s.axis === "right");
  const rows = useMemo(
    () => signals.map((p) => ({ month: p.month, ...Object.fromEntries(active.series.map((s) => [s.key, scale(p[s.key] as number, s.unit)])) })),
    [signals, active],
  );
  const runs = useMemo(() => bandRuns(scoreHistory), [scoreHistory]);
  const bandsSeen = [...new Set(scoreHistory.map((h) => h.band))];

  if (!signals.length) return <EmptyState title="No signals to show" description="Signals appear once the MSME's consent is active. Without consent no data is pulled." />;

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList aria-label="Signal group">
        {TABS.map((t) => (
          <TabsTrigger key={t.key} value={t.key}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value={tab}>
        <ChartFrame
          height={280}
          label={`${active.label}: ${active.series.map((s) => s.label).join(", ")} for ${signals.length} months, ${monthLabel(signals[0].month)} to ${monthLabel(signals[signals.length - 1].month)}`}
        >
          <ResponsiveContainer>
            <ComposedChart data={rows} margin={{ top: 16, right: right ? 0 : 12, left: -8, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              {runs.map((r) => (
                <ReferenceArea key={r.from} yAxisId="left" x1={r.from} x2={r.to} fill={BAND_VAR[r.band]} fillOpacity={0.06} strokeOpacity={0} ifOverflow="extendDomain" />
              ))}
              <XAxis dataKey="month" {...X_AXIS} interval={2} tickFormatter={(m: string) => monthLabel(m).replace(" 20", " ’")} />
              <YAxis yAxisId="left" {...AXIS} tickFormatter={tick(left.unit)} width={48} />
              {right && <YAxis yAxisId="right" orientation="right" {...AXIS} tickFormatter={tick(right.unit)} width={40} allowDecimals={false} />}
              <Tooltip
                {...TOOLTIP}
                labelFormatter={(m: string) => {
                  const h = scoreHistory.find((s) => s.month === m);
                  return `${monthLabel(m)}${h ? ` · score ${h.score}` : ""}`;
                }}
                formatter={(v: number, _n: string, item: { dataKey?: string | number }) => {
                  const s = active.series.find((x) => x.key === item.dataKey)!;
                  return [fmt(v, s.unit), s.label];
                }}
              />
              <Legend {...LEGEND} />
              {stressStart && (
                <ReferenceLine
                  yAxisId="left"
                  x={stressStart.month}
                  stroke="var(--danger)"
                  strokeDasharray="4 3"
                  label={{ value: "Stress began", position: "top", fontSize: 11, fill: "var(--danger)" }}
                />
              )}
              {active.series.map((s, i) =>
                s.kind === "bar" ? (
                  <Bar
                    key={s.key}
                    yAxisId={s.axis ?? "left"}
                    dataKey={s.key}
                    name={s.label}
                    fill={CHART[i]}
                    fillOpacity={0.55}
                    barSize={10}
                    radius={[3, 3, 0, 0]}
                    isAnimationActive={false}
                  />
                ) : (
                  <Line
                    key={s.key}
                    yAxisId={s.axis ?? "left"}
                    type="monotone"
                    dataKey={s.key}
                    name={s.label}
                    stroke={CHART[i]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false}
                  />
                ),
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </ChartFrame>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-muted">
          <span>Background shows the score band each month:</span>
          {bandsSeen.map((b) => (
            <BandPill key={b} band={b} />
          ))}
          {stressStart && (
            <span className="inline-flex items-center gap-1.5">
              · First early-warning signal in {monthLabel(stressStart.month)} <SeverityPill severity={stressStart.severity} />
            </span>
          )}
        </div>
      </TabsContent>
    </Tabs>
  );
}
