import { useCallback, useEffect, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ScoreGauge } from "../components/ScoreGauge";
import { AiLabel, BandChip, ErrorNote } from "../components/ui";
import { api, del, post } from "../lib/api";
import { useAuth } from "../lib/auth";

function ForecastChart({ forecast }: { forecast: any }) {
  const hist = forecast.history.slice(-9).map((h: any) => ({ month: h.month, actual: h.actual / 1e5 }));
  const last = hist[hist.length - 1];
  const fc = forecast.forecast.map((f: any) => ({ month: f.month, forecast: f.yhat / 1e5, range: [f.lo / 1e5, f.hi / 1e5] }));
  const rows = [...hist.slice(0, -1), { ...last, forecast: last.actual, range: [last.actual, last.actual] }, ...fc];
  return (
    <div className="h-48">
      <ResponsiveContainer>
        <ComposedChart data={rows} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
          <CartesianGrid stroke="#eef0f6" vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#6b7088" }} tickLine={false} axisLine={{ stroke: "#e6e8f0" }} />
          <YAxis tick={{ fontSize: 9, fill: "#6b7088" }} tickLine={false} axisLine={false} />
          <ReferenceLine y={0} stroke="#c9cce0" />
          <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={(v: any) => (Array.isArray(v) ? `${v[0].toFixed(1)} – ${v[1].toFixed(1)} lakh` : `₹${Number(v).toFixed(1)} lakh`)} />
          <Legend iconType="plainline" wrapperStyle={{ fontSize: 10 }} />
          <Area dataKey="range" name="80% range" fill="#7B5CFF" fillOpacity={0.12} stroke="none" />
          <Line dataKey="actual" name="Net cash inflow" stroke="#7B5CFF" strokeWidth={2} dot={false} />
          <Line dataKey="forecast" name="Forecast" stroke="#7B5CFF" strokeWidth={2} strokeDasharray="4 3" dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function MsmeApp() {
  const { session } = useAuth();
  const fid = session!.factory_id!;
  const [r, setR] = useState<any>(null);
  const [notes, setNotes] = useState<any[]>([]);
  const [hindi, setHindi] = useState(false);
  const [tab, setTab] = useState<"home" | "plan" | "consent" | "chat">("home");
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, n] = await Promise.all([api(`/msme/${fid}/readiness`), api(`/msme/${fid}/notifications`)]);
      setR(a);
      setNotes(n);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [fid]);
  useEffect(() => {
    load();
    window.addEventListener("sim-advanced", load);
    return () => window.removeEventListener("sim-advanced", load);
  }, [load]);

  async function revoke() {
    await del(`/applications/${r.application_id}/consent`);
    setMsg("Consent revoked. The bank can no longer pull your data; fetched copies are being deleted.");
    await load();
  }
  async function review() {
    await post(`/applications/${r.application_id}/review-request`, { note: "Please review my assessment with a human officer." });
    setMsg("Review requested — a credit officer will get back to you.");
    await load();
  }

  if (!r) return <ErrorNote error={error} />;
  const plan = r.plan;
  return (
    <div className="flex justify-center">
      <div className="w-full max-w-sm overflow-hidden rounded-[2rem] border-8 border-navy bg-white shadow-2xl">
        <div className="bg-navy px-5 pb-4 pt-3 text-white">
          <p className="text-[10px] text-white/60">UdyamPulse · for MSMEs</p>
          <p className="font-semibold">{r.name}</p>
        </div>
        <nav className="grid grid-cols-4 border-b border-line text-xs font-semibold">
          {(["home", "plan", "consent", "chat"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`py-2.5 ${tab === t ? "border-b-2 border-magenta text-magenta" : "text-muted"}`}>
              {{ home: "Readiness", plan: "90-day plan", consent: "Consent", chat: "Messages" }[t]}
              {t === "chat" && notes.length > 0 && <span className="ml-1 rounded-full bg-green px-1.5 text-[10px] text-white">{notes.length}</span>}
            </button>
          ))}
        </nav>
        <div className="max-h-[640px] space-y-4 overflow-y-auto p-4">
          {msg && <p className="rounded-lg bg-violet/10 p-2 text-xs text-violet">{msg}</p>}
          {r.data_stale && <p className="rounded-lg bg-amber/15 p-2 text-xs text-navy">{r.message}</p>}

          {tab === "home" && (
            <>
              <div className="text-center">
                <p className="label">Loan-readiness score</p>
                <ScoreGauge score={r.score} band={r.band} size={240} />
                <div className="mt-1 flex items-center justify-center gap-2 text-xs">
                  <BandChip band={r.band} /> {r.data_month && <span className="text-muted">data through {r.data_month}</span>}
                </div>
              </div>
              {plan && (
                <>
                  <div>
                    <p className="label mb-1">Cash-flow forecast (next 3 months, ₹ lakh)</p>
                    <ForecastChart forecast={plan.forecast} />
                    <p className="text-[10px] text-muted">Model: {plan.forecast.method}. Your average monthly bank inflow is {plan.avg_monthly_credits}.</p>
                  </div>
                  <p className="rounded-lg bg-surface p-3 text-sm">{plan.summary}</p>
                </>
              )}
              <AiLabel />
              {r.decision === "REJECTED" || r.band !== "APPROVE" ? (
                <button className="btn-ghost w-full" disabled={r.review_requested} onClick={review}>
                  {r.review_requested ? "Review requested ✓" : "Request a human review"}
                </button>
              ) : null}
            </>
          )}

          {tab === "plan" && plan && (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-navy">Your 90-day improvement plan</p>
                <button className="rounded-full border border-line px-2 py-0.5 text-xs" onClick={() => setHindi(!hindi)}>
                  {hindi ? "English" : "हिंदी"}
                </button>
              </div>
              {hindi ? (
                <p className="rounded-lg bg-surface p-3 text-sm leading-relaxed">{plan.hindi_summary}</p>
              ) : (
                ["Days 1–30", "Days 31–60", "Days 61–90"].map((ph) => (
                  <div key={ph}>
                    <p className="label mb-1 text-violet">{ph}</p>
                    <ul className="space-y-1.5">
                      {plan.steps
                        .filter((s: any) => s.phase === ph)
                        .map((s: any) => (
                          <li key={s.action} className="flex gap-2 rounded-lg border border-line p-2 text-sm">
                            <span className="text-green">☐</span>
                            {s.action}
                          </li>
                        ))}
                    </ul>
                  </div>
                ))
              )}
              <p className="text-xs text-muted">
                {plan.points_to_target > 0 ? `${plan.points_to_target} points to reach ${plan.target}. ` : ""}
                The issues listed are worth about {plan.recoverable_points} points.
              </p>
              <AiLabel />
            </>
          )}
          {tab === "plan" && !plan && <p className="text-sm text-muted">No plan — data pulls are stopped.</p>}

          {tab === "consent" && (
            <div className="space-y-3 text-sm">
              <div className="rounded-lg border border-line p-3">
                <p className="font-semibold">
                  Account Aggregator + GST consent{" "}
                  {r.consent.active ? <span className="text-green">● Active</span> : <span className="text-magenta">● Not active</span>}
                </p>
                {r.consent.active && (
                  <>
                    <p className="mt-1 text-xs text-muted">Purpose: {r.consent.purpose}</p>
                    <p className="text-xs text-muted">Shared: {r.consent.fi_types.join(", ")}</p>
                    <p className="text-xs text-muted">Valid until {r.consent.expires_on}</p>
                  </>
                )}
              </div>
              {r.consent.active && (
                <button className="btn w-full bg-magenta text-white" onClick={revoke}>
                  Revoke consent
                </button>
              )}
              <p className="text-xs text-muted">
                Revoking stops all future data pulls immediately and deletes copies the bank fetched (DPDP Act 2023). We never collect biometrics.
              </p>
            </div>
          )}

          {tab === "chat" && (
            <div className="space-y-2 rounded-xl bg-[#e9e2d8] p-3">
              <p className="text-center text-[10px] text-black/50">WhatsApp-style notifications (mock)</p>
              {notes.map((n) => (
                <div key={n.id} className="max-w-[90%] rounded-lg rounded-tl-none bg-white p-2 text-xs shadow-sm">
                  <p className="text-[10px] font-semibold text-green">Sample Bank</p>
                  {n.text}
                  <p className="mt-1 text-right text-[9px] text-black/40">{n.sim_date}</p>
                </div>
              ))}
              {notes.length === 0 && <p className="text-center text-xs text-black/50">No messages yet.</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
