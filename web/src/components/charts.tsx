import type { ReactNode } from "react";

/** Shared Recharts styling: soft gridlines, no heavy axes, tooltips on the surface colour. */
export const AXIS = { tick: { fontSize: 11, fill: "var(--text-muted)" }, tickLine: false, axisLine: false } as const;
export const X_AXIS = { ...AXIS, axisLine: { stroke: "var(--border)" } } as const;
export const GRID = { stroke: "var(--border)", strokeDasharray: "0", vertical: false } as const;
export const TOOLTIP = {
  contentStyle: {
    fontSize: 12,
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--surface)",
    color: "var(--text)",
    boxShadow: "0 4px 12px rgba(16,24,40,.08)",
  },
  labelStyle: { color: "var(--text-muted)", marginBottom: 2 },
  itemStyle: { color: "var(--text)", padding: 0 },
  cursor: { stroke: "var(--border-strong)", strokeDasharray: "3 3" },
} as const;
export const LEGEND = { iconType: "plainline", wrapperStyle: { fontSize: 12, color: "var(--text-muted)" } } as const;
export const CHART = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"] as const;

/** Wraps a chart with a text alternative for screen readers. */
export function ChartFrame({ label, height = 260, children }: { label: string; height?: number; children: ReactNode }) {
  return (
    <div role="img" aria-label={label} style={{ height }} className="w-full">
      {children}
    </div>
  );
}
