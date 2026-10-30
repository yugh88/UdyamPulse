import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PillarBars, ReasonList } from "../components/Reasons";
import { ScoreGauge } from "../components/ScoreGauge";
import { SignalChart } from "../components/SignalChart";
import { AiLabel, BandChip, Card, ErrorNote, SeverityChip, Stepper } from "../components/ui";
import { api, del, pdfUrl, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { inr } from "../lib/format";

export default function ApplicationDetail() {
  const { id } = useParams();
  const { session } = useAuth();
  const [app, setApp] = useState<any>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pdf, setPdf] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [memoMs, setMemoMs] = useState<number | null>(null);

  const load = useCallback(() => api(`/applications/${id}`).then(setApp).catch((e) => setError(e.message)), [id]);
  useEffect(() => {
    load();
  }, [load]);

  async function run(label: string, fn: () => Promise<any>) {
    setBusy(label);
    setError(null);
    try {
      const r = await fn();
      if (label === "memo" && r?.generated_in_ms != null) setMemoMs(r.generated_in_ms);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function openPdf() {
    try {
      setPdf(await pdfUrl(`/applications/${id}/memo.pdf`));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!app) return <ErrorNote error={error} />;
  const role = session!.role;
  const sd = app.score_detail;
  const memo = app.memo;
  const canWork = role === "rm" || role === "credit_officer";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/console" className="text-xs text-muted hover:text-navy">
            ← Applications
          </Link>
          <h1 className="text-2xl font-bold text-navy">{app.name}</h1>
          <p className="text-sm text-muted">
            {app.sector} · {app.cluster} · {app.udyam_category} · {app.profile.vintage_years.toFixed(0)} yrs · turnover {app.profile.turnover_band} ·{" "}
            {app.profile.udyam_number} · requested <b className="text-ink">{inr(app.requested_amount)}</b>
          </p>
        </div>
        <Stepper state={app.state} />
      </div>
      <ErrorNote error={error} />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card
          title="Consent (Account Aggregator + GST)"
          actions={
            app.consent.active ? (
              <span className="rounded-full bg-green/10 px-2 py-0.5 text-xs font-semibold text-green">● Active</span>
            ) : (
              <span className="rounded-full bg-line px-2 py-0.5 text-xs font-semibold text-muted">○ Not active</span>
            )
          }
        >
          {app.consent.active ? (
            <dl className="space-y-1 text-xs">
              <div>
                <dt className="label inline">Artefact</dt> <dd className="inline font-mono">{app.consent.consent_id}</dd>
              </div>
              <div>
                <dt className="label inline">Purpose</dt> <dd className="inline">{app.consent.purpose}</dd>
              </div>
              <div>
                <dt className="label inline">Data</dt> <dd className="inline">{app.consent.fi_types.join(", ")}</dd>
              </div>
              <div>
                <dt className="label inline">Expires</dt> <dd className="inline">{app.consent.expires_on}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-muted">No active consent — no data can be pulled.</p>
          )}
          {app.data_checks && (
            <ul className="mt-3 space-y-1 border-t border-line pt-3 text-xs">
              {app.data_checks.map((c: any) => (
                <li key={c.name} className="flex gap-2">
                  <span className={c.status === "pass" ? "text-green" : "text-amber"}>{c.status === "pass" ? "✓" : "!"}</span>
                  <span>
                    <b>{c.name}</b> — {c.detail}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex gap-2">
            {role === "rm" && app.state === "APPLIED" && (
              <button className="btn-primary" disabled={!!busy} onClick={() => run("consent", () => post(`/applications/${id}/consent`))}>
                {busy === "consent" ? "Requesting…" : "Request consent & pull data"}
              </button>
            )}
            {role === "rm" && app.consent.active && (
              <button className="btn-ghost" disabled={!!busy} onClick={() => run("revoke", () => del(`/applications/${id}/consent`))}>
                Revoke
              </button>
            )}
          </div>
        </Card>

        <Card
          title="Factory Health Score"
          actions={
            canWork &&
            ["CONSENTED", "SCORED"].includes(app.state) && (
              <button className="btn-accent" disabled={!!busy} onClick={() => run("score", () => post(`/applications/${id}/score`))}>
                {busy === "score" ? "Scoring…" : sd ? "Re-score" : "Run scoring"}
              </button>
            )
          }
        >
          <ScoreGauge score={sd?.score ?? null} band={sd?.band} />
          {sd && (
            <div className="mt-2 flex flex-col items-center gap-2">
              <div className="flex items-center gap-3 text-sm">
                <BandChip band={sd.band} /> <span className="text-muted">12-month PD</span>
                <b className="tabular-nums">{(sd.pd_12m * 100).toFixed(2)}%</b>
              </div>
              <AiLabel />
            </div>
          )}
        </Card>

        <Card title="Top-5 reasons">{sd ? <ReasonList reasons={sd.reasons} /> : <p className="text-sm text-muted">Run scoring to see SHAP reasons.</p>}</Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Pillar breakdown">{sd ? <PillarBars pillars={sd.pillars} /> : <p className="text-sm text-muted">—</p>}</Card>
        <Card title="24-month operating signals">
          <SignalChart data={app.signals} />
        </Card>
      </div>

      <Card
        title="Credit memo"
        actions={
          <div className="flex items-center gap-2">
            {memoMs != null && <span className="text-xs text-muted">generated in {(memoMs / 1000).toFixed(1)} s</span>}
            {app.memo_pdf_url && (
              <button className="btn-ghost" onClick={openPdf}>
                Preview PDF
              </button>
            )}
            {canWork && ["SCORED", "MEMO_DRAFTED"].includes(app.state) && (
              <button className="btn-accent" disabled={!!busy} onClick={() => run("memo", () => post(`/applications/${id}/memo`))}>
                {busy === "memo" ? "Drafting…" : memo ? "Regenerate memo" : "Generate memo"}
              </button>
            )}
          </div>
        }
      >
        {memo ? (
          <div className="space-y-4">
            <AiLabel />
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-surface p-3">
                <p className="label">Recommended limit</p>
                <p className="text-xl font-bold text-navy">{memo.recommended_limit_display}</p>
                <p className="text-xs text-muted">requested {memo.requested_display}</p>
              </div>
              <div className="rounded-lg bg-surface p-3">
                <p className="label">Pricing band</p>
                <p className="text-lg font-bold text-navy">{memo.pricing_band}</p>
              </div>
              <div className="rounded-lg bg-surface p-3">
                <p className="label">Limit workings</p>
                <p className="text-xs">
                  20% × turnover = {memo.limit_workings.turnover_limit} · band factor {memo.limit_workings.band_factor} · concentration haircut{" "}
                  {memo.limit_workings.concentration_haircut}
                </p>
              </div>
            </div>
            <p className="text-sm leading-relaxed">{memo.summary}</p>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                ["Strengths", memo.strengths, "text-green"],
                ["Risks", memo.risks, "text-magenta"],
                ["Mitigants", memo.mitigants, "text-violet"],
                ["Covenants", memo.covenants, "text-navy"],
              ].map(([title, items, cls]) => (
                <div key={title as string}>
                  <h3 className={`label mb-1.5 ${cls}`}>{title as string}</h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {(items as string[]).map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <details className="rounded-lg border border-line p-3 text-sm">
              <summary className="cursor-pointer font-semibold text-navy">Policy citations ({memo.citations.length}) — retrieved from credit_policy.md</summary>
              <ul className="mt-2 space-y-2">
                {memo.citations.map((c: any) => (
                  <li key={c.section}>
                    <b>
                      [§{c.section}] {c.title}
                    </b>{" "}
                    <span className="text-muted">— {c.excerpt}</span>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        ) : (
          <p className="text-sm text-muted">The credit-memo agent writes prose around numbers from the scoring engine and policy rules — it never invents figures.</p>
        )}
        {pdf && (
          <div className="mt-4">
            <iframe src={pdf} title="Credit memo PDF" className="h-[640px] w-full rounded-lg border border-line" />
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Decision (human-in-the-loop)">
          {app.decision ? (
            <div className="space-y-2 text-sm">
              <p>
                <b className={app.decision === "APPROVED" ? "text-green" : "text-magenta"}>{app.decision}</b> by {app.decided_by}
                {app.sanctioned_limit && <> · sanctioned {inr(app.sanctioned_limit)}</>}
              </p>
              <p className="text-muted">“{app.decision_comment}”</p>
              {app.disbursement_ref && (
                <p>
                  Disbursed via LOS stub · ref <span className="font-mono">{app.disbursement_ref}</span> on {app.disbursed_on}
                </p>
              )}
              {app.state === "DECIDED" && app.decision === "APPROVED" && canWork && (
                <button className="btn-primary" disabled={!!busy} onClick={() => run("disburse", () => post(`/applications/${id}/disburse`))}>
                  Disburse via LOS
                </button>
              )}
            </div>
          ) : role === "credit_officer" ? (
            app.state === "MEMO_DRAFTED" ? (
              <div className="space-y-3">
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Mandatory comment: rationale for your decision"
                  className="h-20 w-full rounded-lg border border-line p-2 text-sm outline-none focus:border-violet"
                />
                <div className="flex gap-2">
                  <button
                    className="btn bg-green text-white"
                    disabled={!!busy || comment.trim().length < 3}
                    onClick={() => run("approve", () => post(`/applications/${id}/decision`, { decision: "APPROVED", comment }))}
                  >
                    Approve
                  </button>
                  <button
                    className="btn bg-magenta text-white"
                    disabled={!!busy || comment.trim().length < 3}
                    onClick={() => run("reject", () => post(`/applications/${id}/decision`, { decision: "REJECTED", comment }))}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted">Waiting for the memo.</p>
            )
          ) : (
            <p className="text-sm text-muted">Only a credit officer can approve or reject. The system only recommends.</p>
          )}
        </Card>
        <Card title="Key Fact Statement (stub)">
          {app.kfs ? (
            <dl className="grid grid-cols-[140px_1fr] gap-x-3 gap-y-1 text-xs">
              {Object.entries(app.kfs).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="label">{k.replace(/_/g, " ")}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-muted">Generated on approval (RBI Digital Lending Directions 2025).</p>
          )}
        </Card>
      </div>

      {app.alerts.length > 0 && (
        <Card title="Early-warning alerts">
          <ul className="space-y-1 text-sm">
            {app.alerts.map((a: any) => (
              <li key={a.id} className="flex items-center gap-3">
                <SeverityChip severity={a.severity} /> {a.month} · next-best action <b>{a.next_best_action}</b> · {a.status}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
