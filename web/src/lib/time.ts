/** "3 min ago", "2 h ago", "5 d ago" from an ISO timestamp. */
export function ago(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "–";
  const s = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

/** "2026-06-30T10:15:00+00:00" → "30 Jun 2026, 10:15" */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

/** "2026-06" → "Jun 2026"; "2026-06-30" → "30 Jun 2026" */
export function monthLabel(ym: string): string {
  const [y, m, d] = ym.split("-").map(Number);
  const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1];
  return d ? `${d} ${mon} ${y}` : `${mon} ${y}`;
}

export const STATE_LABEL: Record<string, string> = {
  APPLIED: "Applied",
  CONSENTED: "Consented",
  SCORED: "Scored",
  MEMO_DRAFTED: "Memo drafted",
  DECIDED: "Decided",
  DISBURSED: "Disbursed",
  MONITORING: "Monitoring",
};
