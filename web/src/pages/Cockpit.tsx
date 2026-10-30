import { Fragment, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AiLabel, BandChip, Card, ErrorNote, Kpi, SeverityChip } from "../components/ui";
import { api, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { inr } from "../lib/format";

const ACTIONS = ["call", "visit", "limit review", "restructure", "visit + limit review"];

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values) - 5;
  const max = Math.max(...values) + 5;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 60},${18 - ((v - min) / (max - min)) * 16}`).join(" ");
  const down = values[values.length - 1] < values[0];
  return (
    <svg width={62} height={20} aria-label={`score trend ${values.join(", ")}`}>
      <polyline points={pts} fill="none" stroke={down ? "#E5397A" : "#2FA866"} strokeWidth={2} strokeLinejoin="round" />
    </svg>
  );
}

/** Sequential single hue (violet): darker cell = lower average score = more risk. */
function cellColor(avg: number): string {
  const t = Math.min(1, Math.max(0, (780 - avg) / 160));
  return `rgba(123, 92, 255, ${0.08 + t * 0.8})`;
}

export default function Cockpit() {
  const { session } = useAuth();
  const [data, setData] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([api("/portfolio"), api("/alerts?status=ALL")]);
      setData(p);
      setAlerts(a);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function advance(days: number) {
    setBusy(true);
    try {
      const r = await post(`/sim/advance?days=${days}`);
      setToast(`Clock → ${r.sim_date} (data through ${r.data_month}). ${r.new_alerts.length} new alert(s)${r.blocked.length ? `, ${r.blocked.length} account(s) blocked by revoked consent` : ""}.`);
      window.dispatchEvent(new Event("sim-advanced"));
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function act(id: number, action: string) {
    await post(`/alerts/${id}/action`, { action, note: `Logged from cockpit by ${session?.username}` });
    await load();
  }

  if (!data) return <ErrorNote error={error} />;
  const k = data.kpis;
  const clusters: string[] = [...new Set<string>(data.heatmap.map((h: any) => h.cluster))].sort();
  const sectors: string[] = [...new Set<string>(data.heatmap.map((h: any) => h.sector))].sort();
  const cell = (c: string, s: string) => data.heatmap.find((h: any) => h.cluster === c && h.sector === s);
  const openAlerts = alerts.filter((a) => a.status === "OPEN");
  const shown = [...openAlerts, ...alerts.filter((a) => a.status !== "OPEN").slice(0, 5)];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-navy">Portfolio risk cockpit</h1>
          <p className="text-sm text-muted">
            {k.accounts} monitored MSME accounts · data through {data.data_month}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-accent" disabled={busy} onClick={() => advance(7)}>
            {busy ? "Advancing…" : "⏩ Fast-forward 1 week"}
          </button>
          <button className="btn-ghost" disabled={busy} onClick={() => advance(42)}>
            +6 weeks
          </button>
        </div>
      </div>
      {toast && <p className="rounded-lg bg-violet/10 px-3 py-2 text-sm text-violet">{toast}</p>}
      <ErrorNote error={error} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Accounts monitored" value={k.accounts} sub={`exposure ${inr(k.exposure)}`} />
        <Kpi label="Average score" value={k.avg_score} sub="Factory Health Score, 300–900" />
        <Kpi
          label="Open alerts by severity"
          value={
            <span className="flex gap-3 text-xl">
              <span className="text-magenta">▲ {k.alerts_by_severity.high}</span>
              <span className="text-[#a5650f]">◆ {k.alerts_by_severity.medium}</span>
              <span className="text-violet">● {k.alerts_by_severity.low}</span>
            </span>
          }
          sub="high · medium · low"
        />
        <Kpi label="Expected slippage avoided (est.)" value={inr(k.expected_slippage_avoided)} sub={<span title={k.slippage_formula}>Σ exposure × PD × LGD × early-action effect ⓘ</span>} />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card title="Average score by cluster × sector" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0.5 text-xs">
              <thead>
                <tr>
                  <th />
                  {sectors.map((s) => (
                    <th key={s} className="px-1 pb-1 text-left font-medium text-muted">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {clusters.map((c) => (
                  <tr key={c}>
                    <th className="pr-2 text-left font-medium text-muted">{c}</th>
                    {sectors.map((s) => {
                      const h = cell(c, s);
                      return (
                        <td
                          key={s}
                          title={h ? `${c} · ${s}: avg ${h.avg_score}, ${h.accounts} accounts, ${h.alerts} open alerts` : "no accounts"}
                          className="h-11 rounded text-center tabular-nums"
                          style={{ background: h ? cellColor(h.avg_score) : "#f6f7fb", color: h && h.avg_score < 700 ? "white" : "#1c2033" }}
                        >
                          {h ? (
                            <>
                              <b>{h.avg_score}</b>
                              <span className="block text-[10px] opacity-80">
                                n={h.accounts}
                                {h.alerts ? ` · ${h.alerts}⚑` : ""}
                              </span>
                            </>
                          ) : (
                            "·"
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-muted">Darker = lower average score. ⚑ = open alerts.</p>
        </Card>

        <Card title={`Alert queue (${openAlerts.length} open)`} className="lg:col-span-3" actions={<AiLabel />}>
          <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
            {shown.length === 0 && <li className="text-sm text-muted">No alerts. Fast-forward the clock to let the early-warning agent scan new data.</li>}
            {shown.map((a) => (
              <li key={a.id} className={`rounded-lg border p-3 ${a.status === "OPEN" ? "border-line" : "border-line/50 opacity-60"}`}>
                <button className="flex w-full items-center gap-3 text-left" onClick={() => setOpen(open === a.id ? null : a.id)}>
                  <SeverityChip severity={a.severity} />
                  <span className="flex-1">
                    <b className="text-sm">{a.name}</b>
                    <span className="text-xs text-muted">
                      {" "}
                      · {a.cluster} · {a.month}
                    </span>
                  </span>
                  <span className="text-xs font-semibold text-navy">→ {a.next_best_action}</span>
                  <span className="text-xs text-muted">{a.status === "OPEN" ? "open" : `✓ ${a.action_taken}`}</span>
                </button>
                {open === a.id && (
                  <div className="mt-3 space-y-2 border-t border-line pt-3 text-sm">
                    <ul className="list-disc pl-5">
                      {a.reasons.map((r: string) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                    <p className="rounded bg-surface p-2 text-xs leading-relaxed">
                      <b>RM briefing:</b> {a.briefing}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link to={`/console/${a.application_id}`} className="text-xs font-semibold text-violet">
                        Open account →
                      </Link>
                      {a.status === "OPEN" &&
                        session?.role !== "risk" &&
                        ACTIONS.map((x) => (
                          <button key={x} className={x === a.next_best_action ? "btn-primary !py-1 text-xs" : "btn-ghost !py-1 text-xs"} onClick={() => act(a.id, x)}>
                            Log: {x}
                          </button>
                        ))}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Monitored accounts">
        <div className="max-h-[420px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-line text-left">
                {["Factory", "Cluster · sector", "Exposure", "Score", "3m Δ", "Trend (6m)", "Band", "Alerts", "Consent"].map((h) => (
                  <th key={h} className="label pb-2 pr-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.accounts.map((r: any) => (
                <Fragment key={r.application_id}>
                  <tr className="border-b border-line/60 hover:bg-surface">
                    <td className="py-2 pr-3">
                      <Link to={`/console/${r.application_id}`} className="font-medium text-navy hover:text-magenta">
                        {r.name}
                      </Link>
                    </td>
                    <td className="pr-3 text-xs text-muted">
                      {r.cluster} · {r.sector}
                    </td>
                    <td className="pr-3 tabular-nums">{inr(r.exposure)}</td>
                    <td className="pr-3 font-semibold tabular-nums">{r.score}</td>
                    <td className={`pr-3 tabular-nums ${r.trend_3m < 0 ? "text-magenta" : "text-green"}`}>
                      {r.trend_3m > 0 ? "+" : ""}
                      {r.trend_3m}
                    </td>
                    <td className="pr-3">
                      <Sparkline values={r.sparkline} />
                    </td>
                    <td className="pr-3">
                      <BandChip band={r.band} />
                    </td>
                    <td className="pr-3">{r.max_severity ? <SeverityChip severity={r.max_severity} /> : <span className="text-muted">–</span>}</td>
                    <td className="text-xs">{r.consent_active ? "active" : <span className="font-semibold text-magenta">revoked</span>}</td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
