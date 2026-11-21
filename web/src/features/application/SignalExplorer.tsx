import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, CHART, ChartFrame, GRID, TOOLTIP, X_AXIS } from "../../components/charts";
import { EmptyState, Segmented, SeverityPill } from "../../components/ui";
import { type Severity } from "../../lib/format";
import { monthLabel } from "../../lib/time";
import type { SignalPoint } from "../../lib/types";

type Unit = "lakh" | "kwh" | "days" | "pct" | "count";
interface Series {
  key: keyof SignalPoint;
  label: string;
  kind?: "line" | "bar";
}
/** One chart per unit, so every chart has a single y-axis (two units become two small charts, never a dual axis). */
interface Panel {
  unit: Unit;
  series: Series[];
}
const GROUPS: { key: string; label: string; panels: Panel[] }[] = [
  {
    key: "orders",
    label: "Orders & dispatch",
    panels: [
      {
        unit: "lakh",
        series: [
          { key: "eway_value", label: "E-way bill value" },
          { key: "einvoice_value", label: "E-invoice value" },
          { key: "open_po_value", label: "Open purchase orders" },
        ],
      },
    ],
  },
  {
    key: "cash",
    label: "Cash flow",
    panels: [
      {
        unit: "lakh",
        series: [
          { key: "aa_credits", label: "Bank inflows" },
          { key: "aa_debits", label: "Bank outflows" },
          { key: "avg_balance", label: "Average balance" },
        ],
      },
      { unit: "count", series: [{ key: "bounces", label: "Cheque/NACH bounces", kind: "bar" }] },
    ],
  },
  {
    key: "production",
    label: "Production",
    panels: [
      { unit: "kwh", series: [{ key: "kwh", label: "Electricity use" }] },
      { unit: "count", series: [{ key: "epfo_headcount", label: "EPFO headcount" }] },
    ],
  },
  {
    key: "buyers",
    label: "Buyers",
    panels: [
      { unit: "days", series: [{ key: "avg_days_to_pay", label: "Days buyers take to pay" }] },
      { unit: "pct", series: [{ key: "top_buyer_share", label: "Top buyer's share of sales" }] },
    ],
  },
  {
    key: "compliance",
    label: "Compliance",
    panels: [
      { unit: "days", series: [{ key: "gst_filing_delay_days", label: "GSTR-3B filing delay", kind: "bar" }] },
      { unit: "pct", series: [{ key: "gst_bank_mismatch", label: "GST vs bank credits gap" }] },
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
const short = (m: string) => monthLabel(m).replace(" 20", " ’");

/** The recent change window: from the first early-warning signal, else the last three months (the window the score
 * compares with the year before). */
export function changeWindow(signals: SignalPoint[], stressStart: { month: string } | null): { from: string; to: string; label: string } | null {
  if (signals.length < 4) return null;
  const to = signals[signals.length - 1].month;
  if (stressStart && signals.some((s) => s.month === stressStart.month)) return { from: stressStart.month, to, label: `Since ${short(stressStart.month)}` };
  return { from: signals[signals.length - 3].month, to, label: "Last 3 months" };
}

function SignalChart({ panel, signals, win, height }: { panel: Panel; signals: SignalPoint[]; win: ReturnType<typeof changeWindow>; height: number }) {
  const rows = useMemo(
    () => signals.map((p) => ({ month: p.month, ...Object.fromEntries(panel.series.map((s) => [s.key, scale(p[s.key] as number, panel.unit)])) })),
    [signals, panel],
  );
  const first = panel.series[0];
  const firstValues = rows.map((r) => (r as unknown as Record<string, number>)[first.key]);
  // Dashed baseline: the 12-month average before the change window.
  const cut = win ? rows.findIndex((r) => r.month === win.from) : rows.length;
  const base = firstValues.slice(Math.max(0, cut - 12), cut > 0 ? cut : rows.length);
  const baseline = base.length ? base.reduce((a, b) => a + b, 0) / base.length : null;
  const last = rows[rows.length - 1] as Record<string, number | string>;

  return (
    <div>
      <ChartFrame
        height={height}
        label={`${panel.series.map((s) => s.label).join(", ")} for ${signals.length} months, ${monthLabel(signals[0].month)} to ${monthLabel(signals[signals.length - 1].month)}. Latest: ${panel.series
          .map((s) => `${s.label} ${fmt(last[s.key] as number, panel.unit)}`)
          .join(", ")}.`}
      >
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 22, right: 16, left: -6, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            {win && (
              <ReferenceArea
                x1={win.from}
                x2={win.to}
                fill="var(--brand-tint)"
                fillOpacity={1}
                strokeOpacity={0}
                ifOverflow="extendDomain"
                label={{ value: win.label, position: "insideTop", fontSize: 12, fontWeight: 600, fill: "var(--brand)" }}
              />
            )}
            <XAxis dataKey="month" {...X_AXIS} interval={Math.max(0, Math.floor(rows.length / 8) - 1)} tickFormatter={short} />
            <YAxis {...AXIS} tickFormatter={tick(panel.unit)} width={52} allowDecimals={panel.unit !== "count"} />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: string) => monthLabel(m)}
              formatter={(v: number, _n: string, item: { dataKey?: string | number }) => {
                const s = panel.series.find((x) => x.key === item.dataKey)!;
                return [fmt(v, panel.unit), s.label];
              }}
            />
            {baseline != null && panel.series.length >= 1 && first.kind !== "bar" && (
              <ReferenceLine y={baseline} stroke="var(--text-subtle)" strokeDasharray="5 4" ifOverflow="extendDomain" />
            )}
            {panel.series.map((s, i) =>
              s.kind === "bar" ? (
                <Bar key={s.key} dataKey={s.key} name={s.label} fill={CHART[i]} barSize={8} radius={[4, 4, 0, 0]} isAnimationActive={false} />
              ) : (
                <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={CHART[i]} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
              ),
            )}
            {panel.series
              .filter((s) => s.kind !== "bar")
              .map((s) => (
                <ReferenceDot
                  key={`end-${s.key}`}
                  x={last.month as string}
                  y={last[s.key] as number}
                  r={5}
                  fill="var(--surface)"
                  stroke={CHART[panel.series.indexOf(s)]}
                  strokeWidth={2.5}
                  isFront
                />
              ))}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>
      <ul className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-13 text-fg-muted">
        {panel.series.map((s, i) => (
          <li key={s.key} className="inline-flex items-center gap-2">
            {s.kind === "bar" ? (
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: CHART[i] }} aria-hidden />
            ) : (
              <span className="h-[3px] w-4 rounded-full" style={{ background: CHART[i] }} aria-hidden />
            )}
            {s.label}
          </li>
        ))}
        {baseline != null && first.kind !== "bar" && (
          <li className="inline-flex items-center gap-2">
            <span className="w-4 border-t-2 border-dashed border-fg-subtle" aria-hidden />
            12-month average of {first.label.toLowerCase()}
          </li>
        )}
      </ul>
    </div>
  );
}

/** One chart at a time, chosen with a segmented control, with the recent change window shaded in pink. */
export function SignalExplorer({ signals, stressStart }: { signals: SignalPoint[]; stressStart: { month: string; severity: Severity } | null }) {
  const [group, setGroup] = useState(GROUPS[0].key);
  const active = GROUPS.find((g) => g.key === group)!;
  const win = useMemo(() => changeWindow(signals, stressStart), [signals, stressStart]);

  if (!signals.length) return <EmptyState title="No signals to show" description="Signals appear once the MSME's consent is active. Without consent no data is pulled." />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Signal group" value={group} onChange={setGroup} options={GROUPS.map((g) => ({ value: g.key, label: g.label }))} />
        {stressStart && (
          <span className="inline-flex items-center gap-2 text-13 text-fg-muted">
            First early-warning signal in {monthLabel(stressStart.month)} <SeverityPill severity={stressStart.severity} />
          </span>
        )}
      </div>
      <div className={active.panels.length > 1 ? "grid gap-6 xl:grid-cols-2" : ""}>
        {active.panels.map((p) => (
          <SignalChart key={`${group}-${p.unit}`} panel={p} signals={signals} win={win} height={active.panels.length > 1 ? 240 : 300} />
        ))}
      </div>
    </div>
  );
}
