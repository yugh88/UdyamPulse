import { useEffect, useState } from "react";
import { Card, ErrorNote, Kpi } from "../components/ui";
import { api } from "../lib/api";

export default function Governance() {
  const [model, setModel] = useState<any>(null);
  const [audit, setAudit] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api("/model"), api("/audit?limit=300")])
      .then(([m, a]) => {
        setModel(m);
        setAudit(a);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (!model) return <ErrorNote error={error} />;
  const t = model.metrics.test;
  const ews = model.ews_backtest;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-navy">Governance</h1>
        <p className="text-sm text-muted">Model inventory, fairness, drift and the full audit trail (RBI FREE-AI: explainable, human-in-the-loop, auditable).</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi label="Hold-out AUC" value={t.auc} sub="out-of-time months 17–24 · target ≥ 0.80" />
        <Kpi label="KS" value={t.ks} sub={`Brier ${t.brier}`} />
        <Kpi label="EWS median lead" value={`${ews.median_lead_days} d`} sub={`before SMA-2 · recall ${ews.recall}`} />
        <Kpi label="Alert precision" value={ews.precision_true_stress} sub={`true stress · SMA-2 within 6m ${ews.precision_sma2_within_6m}`} />
        <Kpi label="Drift" value={model.drift.status} sub={`score PSI ${model.drift.score_psi}`} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        {(["sector", "udyam_category"] as const).map((k) => (
          <Card key={k} title={`Fairness by ${k === "sector" ? "sector" : "micro vs small"}`}>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left">
                  {["Group", "n", "Default", "Approval", "Approval (non-defaulters)", "AIR", "EOR"].map((h) => (
                    <th key={h} className="label pb-1 pr-2">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {model.fairness[k].map((r: any) => (
                  <tr key={r.group} className="border-t border-line">
                    <td className="py-1.5 pr-2 font-medium">{r.group}</td>
                    <td className="pr-2 tabular-nums">{r.n}</td>
                    <td className="pr-2 tabular-nums">{(r.default_rate * 100).toFixed(1)}%</td>
                    <td className="pr-2 tabular-nums">{(r.approval_rate * 100).toFixed(1)}%</td>
                    <td className="pr-2 tabular-nums">{(r.approval_rate_non_defaulters * 100).toFixed(1)}%</td>
                    <td className={`pr-2 tabular-nums ${r.adverse_impact_ratio < 0.8 ? "font-bold text-magenta" : ""}`}>{r.adverse_impact_ratio}</td>
                    <td className={`tabular-nums ${r.equal_opportunity_ratio < 0.8 ? "font-bold text-magenta" : ""}`}>{r.equal_opportunity_ratio}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11px] text-muted">AIR/EOR &lt; 0.8 would be flagged (four-fifths rule). No protected attributes are used.</p>
          </Card>
        ))}
      </div>
      <Card title={`Audit log (latest ${audit.length})`}>
        <div className="max-h-[480px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="text-left">
                {["Time (UTC)", "User", "Role", "Agent", "Tool", "Action", "App", "Inputs (PII-masked)", "Output SHA-256"].map((h) => (
                  <th key={h} className="label pb-1 pr-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id} className="border-t border-line align-top">
                  <td className="py-1 pr-2 whitespace-nowrap tabular-nums">{a.ts.slice(0, 19).replace("T", " ")}</td>
                  <td className="pr-2">{a.user}</td>
                  <td className="pr-2">{a.role}</td>
                  <td className="pr-2">{a.agent}</td>
                  <td className="pr-2 font-mono">{a.tool}</td>
                  <td className="pr-2">{a.action}</td>
                  <td className="pr-2">{a.application_id ?? ""}</td>
                  <td className="max-w-[280px] truncate pr-2 font-mono text-muted" title={JSON.stringify(a.inputs)}>
                    {JSON.stringify(a.inputs)}
                  </td>
                  <td className="font-mono text-muted">{a.output_hash ? a.output_hash.slice(0, 12) + "…" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Model card">
        <pre className="max-h-[480px] overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed">{model.model_card_md}</pre>
      </Card>
    </div>
  );
}
