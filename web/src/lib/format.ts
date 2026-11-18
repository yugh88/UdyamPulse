/** Indian number formatting: lakh/crore grouping (12,34,567) and compact L / Cr helpers. */

const IN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** 1234567 → "12,34,567" */
export function num(value: number | null | undefined, fractionDigits = 0): string {
  if (value == null || Number.isNaN(value)) return "–";
  if (fractionDigits === 0) return IN.format(Math.round(value));
  return new Intl.NumberFormat("en-IN", { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits }).format(value);
}

/** 1234567 → "₹12,34,567" (full precision, for KFS and tables that need exact rupees) */
export function rupees(amount: number | null | undefined): string {
  if (amount == null || Number.isNaN(amount)) return "–";
  return `${amount < 0 ? "−" : ""}₹${IN.format(Math.abs(Math.round(amount)))}`;
}

/** 250000 → "2.5 L" */
export function lakh(amount: number, digits = 1): string {
  return `${(amount / 1e5).toFixed(digits)} L`;
}

/** 30000000 → "3.00 Cr" */
export function crore(amount: number, digits = 2): string {
  return `${(amount / 1e7).toFixed(digits)} Cr`;
}

/** Compact rupees: ≥ 1 Cr → "₹3.00 Cr", ≥ 1 L → "₹2.5 L", else "₹12,345". */
export function inr(amount: number | null | undefined): string {
  if (amount == null || Number.isNaN(amount)) return "–";
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "−" : "";
  if (abs >= 1e7) return `${sign}₹${crore(abs)}`;
  if (abs >= 1e5) return `${sign}₹${lakh(abs)}`;
  return `${sign}₹${IN.format(Math.round(abs))}`;
}

/** 0.0067 → "0.67%" */
export function pct(fraction: number | null | undefined, digits = 1): string {
  if (fraction == null || Number.isNaN(fraction)) return "–";
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** +12 / −5 / 0 with a real minus sign */
export function signed(value: number, digits = 0): string {
  const v = value.toFixed(digits);
  if (value > 0) return `+${v}`;
  if (value < 0) return `−${v.slice(1)}`;
  return v;
}

export type Band = "APPROVE" | "WATCH" | "HIGH_RISK";
export type Severity = "high" | "medium" | "low";

export const BAND_LABEL: Record<Band, string> = { APPROVE: "Approve", WATCH: "Watch", HIGH_RISK: "High risk" };
/** CSS variable per band, for SVG fills and strokes. */
export const BAND_VAR: Record<Band, string> = { APPROVE: "var(--success)", WATCH: "var(--warning)", HIGH_RISK: "var(--danger)" };

export const PILLAR_COLORS: Record<string, string> = {
  order_book: "var(--chart-1)",
  cash_flow: "var(--chart-2)",
  production: "var(--chart-3)",
  receivables: "var(--chart-4)",
  compliance: "var(--chart-5)",
};
