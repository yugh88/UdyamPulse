import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Point {
  month: string;
  eway_value: number;
  kwh: number;
  aa_credits: number;
}

const SERIES = [
  { key: "eway", label: "E-way bill value", color: "#7B5CFF" },
  { key: "kwh", label: "Electricity (kWh)", color: "#E5397A" },
  { key: "aa", label: "AA bank inflow", color: "#F0A040" },
];

/** Three signals on different units, indexed to their first 6-month average = 100 (one shared axis). */
export function SignalChart({ data }: { data: Point[] }) {
  if (!data.length) return <p className="text-sm text-muted">No data visible — consent is not active.</p>;
  const base = (k: keyof Point) => data.slice(0, 6).reduce((s, d) => s + (d[k] as number), 0) / Math.min(6, data.length);
  const b = { eway: base("eway_value"), kwh: base("kwh"), aa: base("aa_credits") };
  const rows = data.map((d) => ({
    month: d.month,
    eway: Math.round((d.eway_value / b.eway) * 100),
    kwh: Math.round((d.kwh / b.kwh) * 100),
    aa: Math.round((d.aa_credits / b.aa) * 100),
  }));
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <CartesianGrid stroke="#eef0f6" vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#6b7088" }} tickLine={false} axisLine={{ stroke: "#e6e8f0" }} interval={2} />
          <YAxis tick={{ fontSize: 10, fill: "#6b7088" }} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
          <ReferenceLine y={100} stroke="#c9cce0" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, borderColor: "#e6e8f0" }}
            formatter={(v: number, name: string) => [`${v}`, name]}
          />
          <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
          {SERIES.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <p className="-mt-1 text-[11px] text-muted">Index: first 6 months = 100.</p>
    </div>
  );
}
