import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CircleCheck, Flag, ShieldCheck, ShieldOff, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  Badge,
  BandPill,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  ScoreGauge,
  SeverityPill,
  Skeleton,
  Stepper,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui";
import { DecisionPanel, type DecisionInput } from "../features/application/Decision";
import { MemoView } from "../features/application/Memo";
import { PillarBars, ReasonCards } from "../features/application/Score";
import { SignalExplorer } from "../features/application/SignalExplorer";
import { WhatIf } from "../features/application/WhatIf";
import { api, ApiError, del, post } from "../lib/api";
import { ASYNC, runJob } from "../lib/jobs";
import { useAuth, type Role } from "../lib/auth";
import { inr, pct } from "../lib/format";
import { monthLabel } from "../lib/time";
import type { AppDetail } from "../lib/types";

type Step = "consent" | "score" | "memo" | "disburse";

function nextStep(app: AppDetail, role: Role): { text: string; action?: Step; label?: string; tab?: string } {
  const worker = role === "rm" || role === "credit_officer";
  switch (app.state) {
    case "APPLIED":
      return role === "rm"
        ? { text: "Ask the MSME for consent through the Account Aggregator, then pull and reconcile its data.", action: "consent", label: "Request consent and pull data" }
        : { text: "Waiting for the relationship manager to take consent." };
    case "CONSENTED":
      return worker ? { text: "Consent is active and the data checks are done. Score the factory.", action: "score", label: "Run scoring" } : { text: "Waiting for scoring." };
    case "SCORED":
      return worker
        ? { text: "The score is ready. Draft the credit memo with policy citations.", action: "memo", label: "Generate memo" }
        : { text: "Waiting for the credit memo." };
    case "MEMO_DRAFTED":
      return role === "credit_officer"
        ? { text: "The memo is ready for your decision.", tab: "memo", label: "Review memo and decide" }
        : { text: "The memo is with the credit officer for a decision.", tab: "memo", label: "View memo" };
    case "DECIDED":
      return app.decision === "APPROVED" && worker
        ? { text: "Approved. Disburse directly to the borrower's own account.", action: "disburse", label: "Disburse via LOS" }
        : { text: app.decision === "REJECTED" ? "Rejected. The MSME has been told the reasons and given a 90-day plan." : "Approved. Waiting for disbursal." };
    default:
      return { text: "Disbursed and under continuous early-warning monitoring." };
  }
}

const CHECK_ICON = {
  pass: <CircleCheck className="h-4 w-4 text-success" aria-hidden />,
  warn: <TriangleAlert className="h-4 w-4 text-warning" aria-hidden />,
  fail: <TriangleAlert className="h-4 w-4 text-danger" aria-hidden />,
};
const CHECK_WORD = { pass: "Pass", warn: "Check", fail: "Fail" };

export default function ApplicationDetail() {
  const { id } = useParams();
  const appId = Number(id);
  const { session } = useAuth();
  const role = session!.role;
  const qc = useQueryClient();
  const [tab, setTab] = useState("assessment");
  const [revoking, setRevoking] = useState(false);

  const q = useQuery({ queryKey: ["application", appId], queryFn: () => api<AppDetail>(`/applications/${appId}`), enabled: Number.isFinite(appId) });

  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["application", appId] }),
      qc.invalidateQueries({ queryKey: ["applications"] }),
      qc.invalidateQueries({ queryKey: ["simulate", appId] }),
    ]);
  const fail = (what: string) => (e: unknown) => {
    toast.error(`${what} failed: ${(e as Error).message}`);
  };

  const consent = useMutation({
    mutationFn: () => post(`/applications/${appId}/consent`),
    onSuccess: () => (toast.success("Consent received. Data pulled and reconciled."), refresh()),
    onError: fail("Consent"),
  });
  const score = useMutation({
    mutationFn: () => runJob<{ score: number; band: string }>(`/applications/${appId}/score`, undefined, { headers: ASYNC }),
    onSuccess: (r) => (toast.success(`Scored ${r.score}`), refresh()),
    onError: fail("Scoring"),
  });
  const memo = useMutation({
    mutationFn: () => runJob<{ generated_in_ms: number; citations: number }>(`/applications/${appId}/memo`, undefined, { headers: ASYNC }),
    onSuccess: (r) => {
      toast.success(`Memo drafted in ${r.generated_in_ms} ms with ${r.citations} policy citations`);
      setTab("memo");
      return refresh();
    },
    onError: fail("Memo"),
  });
  const decide = useMutation({
    mutationFn: (d: DecisionInput) => post(`/applications/${appId}/decision`, d),
    onSuccess: (_r, d) => (toast.success(d.decision === "APPROVED" ? "Approved. Key Fact Statement issued." : "Application rejected."), refresh()),
    onError: fail("Decision"),
  });
  const disburse = useMutation({
    mutationFn: () => post<{ disbursement_ref: string }>(`/applications/${appId}/disburse`),
    onSuccess: (r) => (toast.success(`Disbursed (ref ${r.disbursement_ref}). Monitoring has started.`), refresh()),
    onError: fail("Disbursal"),
  });
  const revoke = useMutation({
    mutationFn: () => del(`/applications/${appId}/consent`),
    onSuccess: () => (toast.success("Consent revoked. Data pulls stopped and stored copies deleted."), setRevoking(false), refresh()),
    onError: fail("Revocation"),
  });
  const run: Record<Step, { go: () => void; busy: boolean }> = {
    consent: { go: () => consent.mutate(), busy: consent.isPending },
    score: { go: () => score.mutate(), busy: score.isPending },
    memo: { go: () => memo.mutate(), busy: memo.isPending },
    disburse: { go: () => disburse.mutate(), busy: disburse.isPending },
  };

  if (q.isLoading)
    return (
      <div className="space-y-5" role="status" aria-label="Loading application">
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-16" />
        <div className="grid gap-5 lg:grid-cols-[320px_1fr_300px]">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  if (q.isError || !q.data) {
    const notFound = q.error instanceof ApiError && q.error.status === 404;
    return notFound ? (
      <EmptyState
        title="Application not found"
        description={`There is no application #${id}.`}
        action={
          <Link to="/console" className="text-sm font-medium text-primary hover:underline">
            Back to applications
          </Link>
        }
      />
    ) : (
      <ErrorState error={q.error} onRetry={() => q.refetch()} />
    );
  }

  const app = q.data;
  const sd = app.score_detail;
  const next = nextStep(app, role);
  const worker = role === "rm" || role === "credit_officer";
  const canMemo = worker && (app.state === "SCORED" || app.state === "MEMO_DRAFTED");
  const openAlerts = app.alerts.filter((a) => a.status === "OPEN");

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-fg">{app.name}</h1>
            {app.band && <BandPill band={app.band} />}
            {app.review_requested && (
              <Badge tone="warning" icon={<Flag className="h-3 w-3" aria-hidden />}>
                Human review requested
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-fg-muted">
            {app.sector} · {app.cluster} · {app.udyam_category} enterprise · {Math.round(app.profile.vintage_years)} years in business · turnover {app.profile.turnover_band} ·
            requested <span className="tabular font-medium text-fg">{inr(app.requested_amount)}</span>
          </p>
        </div>
      </header>

      <Card className="space-y-4">
        <Stepper current={app.state} />
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-control bg-panel-2 px-4 py-3">
          <p className="text-sm text-fg">
            <span className="font-semibold">Next: </span>
            {next.text}
          </p>
          {next.action ? (
            <Button variant="primary" loading={run[next.action].busy} onClick={run[next.action].go} icon={<ArrowRight className="h-4 w-4" aria-hidden />}>
              {next.label}
            </Button>
          ) : next.tab ? (
            <Button variant="primary" onClick={() => setTab(next.tab!)} icon={<ArrowRight className="h-4 w-4" aria-hidden />}>
              {next.label}
            </Button>
          ) : app.state === "MONITORING" ? (
            <Link to="/cockpit" className="text-sm font-medium text-primary hover:underline">
              Open the risk cockpit
            </Link>
          ) : null}
        </div>
      </Card>

      {app.review_requested && app.review_note && (
        <p className="rounded-control border border-edge bg-warning-tint px-4 py-3 text-sm text-fg">
          <span className="font-semibold">The MSME asked for a human review: </span>“{app.review_note}”
        </p>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="assessment">Assessment</TabsTrigger>
          <TabsTrigger value="memo">Memo and decision</TabsTrigger>
          <TabsTrigger value="whatif">What-if simulator</TabsTrigger>
        </TabsList>

        <TabsContent value="assessment">
          <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_300px]">
            <div className="space-y-5">
              <Card title="Factory Health Score">
                <ScoreGauge score={app.score} band={app.band} />
                {sd ? (
                  <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
                    {[
                      ["12-month PD", pct(sd.pd_12m, 2)],
                      [
                        "Data as of",
                        app.score_history.length
                          ? monthLabel(app.score_history[Math.min(sd.month, app.score_history.length) - 1]?.month ?? app.score_history[0].month)
                          : `month ${sd.month}`,
                      ],
                      ["Model", "udyampulse-pd"],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-control bg-panel-2 px-2 py-2">
                        <dt className="text-xs text-fg-muted">{k}</dt>
                        <dd className="tabular text-13 font-semibold text-fg">{v}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="mt-3 text-center text-13 text-fg-muted">Not scored yet.</p>
                )}
              </Card>
              {sd && (
                <>
                  <Card title="Top 5 reasons" description="What moved the score most, in plain language">
                    <ReasonCards reasons={sd.reasons} />
                  </Card>
                  <Card title="Pillar breakdown">
                    <PillarBars pillars={sd.pillars} />
                  </Card>
                </>
              )}
            </div>

            <div className="min-w-0 space-y-5">
              <Card title="Signal explorer" description={app.signals.length ? `${app.signals.length} months of consented operating data` : undefined}>
                <SignalExplorer signals={app.signals} scoreHistory={app.score_history} stressStart={app.stress_start} />
              </Card>
              {openAlerts.length > 0 && (
                <Card title="Open early-warning alerts">
                  <ul className="divide-y divide-edge">
                    {openAlerts.map((a) => (
                      <li key={a.id} className="flex items-center gap-3 py-2 text-13">
                        <SeverityPill severity={a.severity} />
                        <span className="text-fg">{monthLabel(a.month)}</span>
                        <span className="text-fg-muted">Next-best action: {a.next_best_action}</span>
                        <Link to={`/cockpit?alert=${a.id}`} className="ml-auto font-medium text-primary hover:underline">
                          Open alert
                        </Link>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>

            <div className="space-y-5">
              <Card
                title="Consent"
                actions={
                  app.consent.active ? (
                    <Badge tone="success" icon={<ShieldCheck className="h-3.5 w-3.5" aria-hidden />}>
                      Active
                    </Badge>
                  ) : (
                    <Badge tone={app.consent.status === "REVOKED" ? "danger" : "neutral"} icon={<ShieldOff className="h-3.5 w-3.5" aria-hidden />}>
                      {app.consent.status === "REVOKED" ? "Revoked" : "Not given"}
                    </Badge>
                  )
                }
              >
                {app.consent.active ? (
                  <>
                    <dl className="grid grid-cols-2 gap-x-2 gap-y-2 text-13">
                      <div className="col-span-2">
                        <dt className="text-xs text-fg-muted">Purpose</dt>
                        <dd className="text-fg">{app.consent.purpose}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-fg-muted">Expires</dt>
                        <dd className="tabular text-fg">{app.consent.expires_on}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-fg-muted">Fetch frequency</dt>
                        <dd className="text-fg">{app.consent.frequency?.toLowerCase()}</dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-xs text-fg-muted">Data types</dt>
                        <dd className="mt-1 flex flex-wrap gap-1">
                          {app.consent.fi_types?.map((t) => (
                            <Badge key={t}>{t.replace(/_/g, " ").toLowerCase()}</Badge>
                          ))}
                        </dd>
                      </div>
                    </dl>
                    {role === "rm" && (
                      <Button size="sm" className="mt-4" onClick={() => setRevoking(true)}>
                        Revoke on the MSME's request
                      </Button>
                    )}
                  </>
                ) : (
                  <p className="text-13 text-fg-muted">
                    {app.consent.status === "REVOKED"
                      ? "Consent was revoked. No new data is pulled and stored copies were deleted."
                      : "No data can be pulled until the MSME gives consent."}
                  </p>
                )}
              </Card>

              <Card title="Data quality and reconciliation">
                {app.data_checks?.length ? (
                  <ul className="space-y-2.5">
                    {app.data_checks.map((c) => (
                      <li key={c.name} className="flex gap-2.5">
                        <span className="mt-0.5 shrink-0">{CHECK_ICON[c.status]}</span>
                        <div className="min-w-0">
                          <p className="text-13 font-medium text-fg">
                            {c.name} <span className="font-normal text-fg-muted">· {CHECK_WORD[c.status]}</span>
                          </p>
                          <p className="text-xs text-fg-muted">{c.detail}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-13 text-fg-muted">Checks run when data is pulled.</p>
                )}
              </Card>

              <Card title="Peer comparison" description={app.peers ? `Against the median of ${app.peers.peer_count} factories in ${app.peers.cluster}` : undefined}>
                {app.peers?.rows.length ? (
                  <table className="w-full text-13">
                    <thead>
                      <tr className="text-left text-xs text-fg-muted">
                        <th scope="col" className="pb-1.5 font-medium">
                          Metric
                        </th>
                        <th scope="col" className="pb-1.5 text-right font-medium">
                          This unit
                        </th>
                        <th scope="col" className="pb-1.5 text-right font-medium">
                          Cluster
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {app.peers.rows.map((r) => (
                        <tr key={r.metric} className="border-t border-edge">
                          <th scope="row" className="py-1.5 pr-2 text-left font-normal text-fg">
                            {r.label}
                          </th>
                          <td className="py-1.5 text-right font-semibold text-fg">{r.value}</td>
                          <td className="py-1.5 pl-2 text-right text-fg-muted">{r.peer_median}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-13 text-fg-muted">Available once consent is active.</p>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="memo">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
            <MemoView
              applicationId={app.id}
              memo={app.memo}
              canGenerate={canMemo}
              generating={memo.isPending}
              onGenerate={() => memo.mutate()}
              generateHint={!sd ? "Score the application first. The memo is built from the score." : undefined}
            />
            <DecisionPanel
              key={`${app.state}-${app.recommended_limit}`}
              app={app}
              role={role}
              deciding={decide.isPending}
              disbursing={disburse.isPending}
              onDecide={(d) => decide.mutateAsync(d)}
              onDisburse={() => disburse.mutate()}
            />
          </div>
        </TabsContent>

        <TabsContent value="whatif">
          {app.consent.active ? (
            <WhatIf applicationId={app.id} />
          ) : (
            <EmptyState title="Simulator unavailable" description="The simulator reads the factory's consented data. It needs an active consent." />
          )}
        </TabsContent>
      </Tabs>

      <Dialog
        open={revoking}
        onOpenChange={setRevoking}
        title="Revoke consent?"
        description="Do this only when the MSME has asked for it."
        footer={
          <>
            <Button onClick={() => setRevoking(false)} disabled={revoke.isPending}>
              Keep consent
            </Button>
            <Button variant="danger" loading={revoke.isPending} onClick={() => revoke.mutate()}>
              Revoke consent
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg">
          New data pulls stop immediately, stored copies are deleted, and scoring and monitoring for this account are blocked until consent is given again.
        </p>
      </Dialog>
    </div>
  );
}
