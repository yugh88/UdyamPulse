export function inr(amount: number | null | undefined): string {
  if (amount == null) return "–";
  if (Math.abs(amount) >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (Math.abs(amount) >= 1e5) return `₹${(amount / 1e5).toFixed(1)} lakh`;
  return `₹${Math.round(amount).toLocaleString("en-IN")}`;
}

export const BAND_STYLE: Record<string, { label: string; cls: string; color: string }> = {
  APPROVE: { label: "Approve", cls: "bg-green/10 text-green ring-green/30", color: "#2FA866" },
  WATCH: { label: "Watch", cls: "bg-amber/15 text-[#a5650f] ring-amber/40", color: "#F0A040" },
  HIGH_RISK: { label: "High risk", cls: "bg-magenta/10 text-magenta ring-magenta/30", color: "#E5397A" },
};

export const SEVERITY_STYLE: Record<string, { cls: string; icon: string }> = {
  high: { cls: "bg-magenta text-white", icon: "▲" },
  medium: { cls: "bg-amber text-navy", icon: "◆" },
  low: { cls: "bg-violet/15 text-violet", icon: "●" },
};

export const PILLAR_COLORS: Record<string, string> = {
  order_book: "#7B5CFF",
  cash_flow: "#E5397A",
  production: "#F0A040",
  receivables: "#2FA866",
  compliance: "#0B1033",
};
