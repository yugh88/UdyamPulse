import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Banknote, BellRing, CircleCheck, FileDown, FlaskConical, Flag, Gavel, ShieldCheck, ShieldOff, TriangleAlert } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Delta, WhatChanged } from "../components/change";
import {
  Badge,
  BandPill,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  ScoreGauge,
  Sheet,
  Skeleton,
  Stepper,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  useUrlTab,
} from "../components/ui";
import { AgentTrace } from "../features/application/AgentTrace";
import { DecisionPanel, MemoSummary, type DecisionInput } from "../features/application/Decision";
import { downloadMemo, MemoView, PolicySheet } from "../features/application/Memo";
import { SignalExplorer } from "../features/application/SignalExplorer";
import { WhatIf } from "../features/application/WhatIf";
import { WhyScore } from "../features/application/WhyScore";
import { api, ApiError, del, post } from "../lib/api";
import { nextStepSentence } from "../lib/alerts";
import { useAuth, type Role } from "../lib/auth";
import { inr, pct } from "../lib/format";
import { ASYNC, runJob } from "../lib/jobs";
import { monthLabel } from "../lib/time";
import type { AppDetail, ChangeEvent } from "../lib/types";

const TABS = ["overview", "signals", "memo", "decision", "activity"] as const;
const TAB_LABEL: Record<(typeof TABS)[number], string> = { overview: "Overview", signals: "Signals", memo: "Credit memo", decision: "Decision", activity: "Activity" };

type Action = "consent" | "score" | "memo" | "disburse" | "decide";

/** The one primary action for this role at this step (never more than one). */
function primaryAction(app: AppDetail, role: Role): { action: Action; label: string } | null {
  const worker = role === "rm" || role === "credit_officer";
  switch (app.state) {
    case "APPLIED":
      return role === "rm" ? { action: "consent", label: "Request consent and pull data" } : null;
    case "CONSENTED":
      return worker ? { action: "score", label: "Run scoring" } : null;
    case "SCORED":
      return worker ? { action: "memo", label: "Generate memo" } : null;
    case "MEMO_DRAFTED":
      return role === "credit_officer" ? { action: "decide", label: "Review & decide" } : null;
    case "DECIDED":
      return app.decision === "APPROVED" && worker ? { action: "disburse", label: "Disburse via LOS" } : null;
    default:
      return null;
  }
}

const ACTION_ICON: Record<Action, ReactNode> = {
  consent: <ShieldCheck className="h-4 w-4" aria-hidden />,
  score: <ArrowRight className="h-4 w-4" aria-hidden />,
  memo: <ArrowRight className="h-4 w-4" aria-hidden />,
  decide: <Gavel className="h-4 w-4" aria-hidden />,
  disburse: <Banknote className="h-4 w-4" aria-hidden />,
};

const CHECK_ICON = {
  pass: <CircleCheck className="h-4 w-4 text-success" aria-hidden />,
  warn: <TriangleAlert className="h-4 w-4 text-warning" aria-hidden />,
  fail: <TriangleAlert className="h-4 w-4 text-danger" aria-hidden />,
};
const CHECK_WORD = { pass: "Pass", warn: "Check", fail: "Fail" };

function HealthCard({ app, onScore, canScore, scoring }: { app: AppDetail; onScore: () => void; canScore: boolean; scoring: boolean }) {
  const hist = app.score_history;
  const prev = hist.length >= 2 ? hist[hist.length - 2] : null;
  if (app.score == null)
    return (
      <Card title="Health score">
        <EmptyState
          title="Not scored yet"
          description={app.consent.active ? "Consent is on and the data is in. Now run the score." : "The owner needs to give consent and share data first."}
          action={
            canScore && app.state === "CONSENTED" ? (
              <Button variant="primary" loading={scoring} onClick={onScore}>
                Run scoring
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  return (
    <Card title="Health score">
      <ScoreGauge score={app.score} band={app.band} previous={prev?.score ?? null} size={260} />
      <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
        <BandPill band={app.band} />
        {prev && <Delta before={prev.score} after={app.score} goodWhenUp suffix={`since ${monthLabel(prev.month).split(" ")[0]}`} />}
      </div>
      {prev && <p className="mt-3 text-center text-sm text-fg-muted">Grey dot = last month ({prev.score})</p>}
      <dl className="mt-5 grid grid-cols-2 border-t border-edge pt-5 text-center">
        <div>
          <dt className="label-caps">Suggested limit</dt>
          <dd className="tabular mt-1 text-xl font-bold text-fg">{app.recommended_limit != null ? inr(app.recommended_limit) : "after memo"}</dd>
        </div>
        <div>
          <dt className="label-caps">Risk of default</dt>
          <dd className="tabular mt-1 text-xl font-bold text-fg">{pct(app.pd_12m, 1)}</dd>
        </div>
      </dl>
    </Card>
  );
}

export default function ApplicationDetail() {
  const { id } = useParams();
  const appId = Number(id);
  const { session } = useAuth();
  const role = session!.role;
  const qc = useQueryClient();
  const [tab, setTab] = useUrlTab(TABS, "overview");
  const [revoking, setRevoking] = useState(false);
  const [whatIf, setWhatIf] = useState(false);
  const [policy, setPolicy] = useState<string | null>(null);

  const q = useQuery({ queryKey: ["application", appId], queryFn: () => api<AppDetail>(`/applications/${appId}`), enabled: Number.isFinite(appId) });
  const changes = useQuery({ queryKey: ["changes", appId], queryFn: () => api<ChangeEvent[]>(`/applications/${appId}/changes?limit=200`), enabled: Number.isFinite(appId) });

  // Opening the application marks it seen: the list's change markers clear. The timeline keeps its "New" badges
  // for this visit, so the user can still see what changed.
  useEffect(() => {
    if (!q.data) return;
    void post("/seen", { entity_type: "application", ids: [String(appId)] })
      .then(() => {
        void qc.invalidateQueries({ queryKey: ["applications"] });
        void qc.invalidateQueries({ queryKey: ["nav-counts"] });
      })
      .catch(() => undefined);
  }, [q.data?.id, appId, qc]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = () =>
    Promise.all(
      ["application", "applications", "changes", "simulate", "nav-counts"].map((k) =>
        qc.invalidateQueries({ queryKey: k === "application" || k === "changes" || k === "simulate" ? [k, appId] : [k] }),
      ),
    );
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
    onSuccess: (r) => {
      const before = q.data?.score;
      toast.success(before != null && before !== r.score ? `Score updated · ${before} → ${r.score}` : `Scored ${r.score}`);
      return refresh();
    },
    onError: fail("Scoring"),
  });
  const memo = useMutation({
    mutationFn: () => runJob<{ generated_in_ms: number; citations: number }>(`/applications/${appId}/memo`, undefined, { headers: ASYNC }),
    onSuccess: (r) => {
      toast.success(`Memo ready · drafted in ${r.generated_in_ms} ms with ${r.citations} policy citations`);
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
    onSuccess: () => (toast.success("Consent revoked. No new data will be collected, and stored copies are deleted."), setRevoking(false), refresh()),
    onError: fail("Revocation"),
  });

  if (q.isLoading)
    return (
      <div className="space-y-6" role="status" aria-label="Loading application">
        <Skeleton className="h-4 w-60" />
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-24" />
        <div className="grid gap-5 lg:grid-cols-3">
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
  const worker = role === "rm" || role === "credit_officer";
  const primary = primaryAction(app, role);
  const busy: Record<Action, boolean> = { consent: consent.isPending, score: score.isPending, memo: memo.isPending, disburse: disburse.isPending, decide: false };
  const run = (a: Action) => {
    if (a === "consent") consent.mutate();
    else if (a === "score") score.mutate();
    else if (a === "memo") memo.mutate();
    else if (a === "disburse") disburse.mutate();
    else setTab("decision");
  };
  const openAlerts = app.alerts.filter((a) => a.status === "OPEN");
  const decidedDone = app.state === "DECIDED" || app.state === "DISBURSED" || app.state === "MONITORING";
  const canMemo = worker && (app.state === "SCORED" || app.state === "MEMO_DRAFTED");

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: "Applications", to: role === "risk" ? "/portfolio?tab=exposure" : "/console" }, { label: app.name }]}
        title={app.name}
        description={
          <>
            {app.cluster} · {app.sector} · {app.udyam_category} enterprise · asks for <span className="tabular font-medium text-fg">{inr(app.requested_amount)}</span>
          </>
        }
        actions={
          tab === "decision" ? (
            app.band ? (
              <span className="flex items-center">
                <span className="sr-only">AI recommendation: </span>
                <BandPill band={app.band} className="px-3.5 py-1.5 text-sm" />
              </span>
            ) : undefined
          ) : (
            <>
              {app.memo && (
                <Button size="lg" onClick={() => downloadMemo(app.id)} icon={<FileDown className="h-4 w-4" aria-hidden />}>
                  Download memo
                </Button>
              )}
              {primary && (
                <Button variant="primary" size="lg" loading={busy[primary.action]} onClick={() => run(primary.action)} icon={ACTION_ICON[primary.action]}>
                  {primary.label}
                </Button>
              )}
            </>
          )
        }
      />

      {/* The Decision tab is about the memo and the decision only, so it leaves the progress stepper out. */}
      {tab === "decision" && app.state === "MONITORING" && <p className="text-13 text-fg-muted">Disbursed and under continuous early-warning monitoring.</p>}
      {tab !== "decision" && (
        <Card className="py-5">
          <Stepper current={app.state} complete={decidedDone} />
          {app.state === "MONITORING" && <p className="mt-3 text-center text-13 text-fg-muted">Disbursed and under continuous early-warning monitoring.</p>}
        </Card>
      )}

      {(app.review_requested || openAlerts.length > 0) && (
        <div className="space-y-2">
          {app.review_requested && (
            <p className="flex items-start gap-2 rounded-control bg-warning-tint px-4 py-2.5 text-sm text-fg">
              <Flag className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
              <span>
                <span className="font-semibold">The owner asked for a human review</span>
                {app.review_note ? `: “${app.review_note}”` : "."}
              </span>
            </p>
          )}
          {openAlerts.length > 0 && (
            <p className="flex flex-wrap items-center gap-2 rounded-control bg-danger-tint px-4 py-2.5 text-sm text-fg">
              <BellRing className="h-4 w-4 shrink-0 text-danger" aria-hidden />
              <span className="font-semibold">
                {openAlerts.length} open early-warning alert{openAlerts.length === 1 ? "" : "s"}
              </span>
              <span className="text-fg-muted">· {nextStepSentence(openAlerts[0].next_best_action)}</span>
              <Link to={`/alerts?alert=${openAlerts[0].id}`} className="ml-auto font-semibold text-danger hover:underline">
                Open alert
              </Link>
            </p>
          )}
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Application sections">
          {TABS.map((t) => (
            <TabsTrigger key={t} value={t} className="text-[15px]">
              {TAB_LABEL[t]}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.15fr)_minmax(0,1.1fr)]">
            <HealthCard app={app} canScore={worker} scoring={score.isPending} onScore={() => score.mutate()} />
            <Card title="Why this score" description="Top reasons, in plain words">
              {sd ? (
                <>
                  <WhyScore reasons={sd.reasons} />
                  <button type="button" onClick={() => setTab("signals")} className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-info hover:underline">
                    See all signals <ArrowRight className="h-4 w-4" aria-hidden />
                  </button>
                </>
              ) : (
                <p className="text-13 text-fg-muted">Reasons show after the factory is scored.</p>
              )}
            </Card>
            <Card title="What changed" description="Latest first">
              <WhatChanged items={changes.data} loading={changes.isLoading} limit={5} />
              {(changes.data?.length ?? 0) > 5 && (
                <button type="button" onClick={() => setTab("activity")} className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-info hover:underline">
                  All activity <ArrowRight className="h-4 w-4" aria-hidden />
                </button>
              )}
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="signals">
          <div className="space-y-5">
            <Card
              title="Signals"
              description={app.signals.length ? `${app.signals.length} months of data shared with consent · pink = recent change` : undefined}
              actions={
                app.consent.active && worker ? (
                  <Button size="sm" onClick={() => setWhatIf(true)} icon={<FlaskConical className="h-4 w-4" aria-hidden />}>
                    Try a what-if
                  </Button>
                ) : undefined
              }
            >
              <SignalExplorer signals={app.signals} stressStart={app.stress_start} />
            </Card>
            <div className="grid gap-5 lg:grid-cols-2">
              <Card
                title="Consent and data checks"
                actions={
                  app.consent.active ? (
                    <Badge tone="success" icon={<ShieldCheck className="h-3.5 w-3.5" aria-hidden />}>
                      Consent active
                    </Badge>
                  ) : (
                    <Badge tone={app.consent.status === "REVOKED" ? "danger" : "neutral"} icon={<ShieldOff className="h-3.5 w-3.5" aria-hidden />}>
                      {app.consent.status === "REVOKED" ? "Consent revoked" : "No consent yet"}
                    </Badge>
                  )
                }
              >
                {app.consent.active && (
                  <p className="mb-4 text-13 text-fg-muted">
                    {app.consent.purpose} · until <span className="tabular">{app.consent.expires_on}</span> ·{" "}
                    {app.consent.fi_types?.map((t) => t.replace(/_/g, " ").toLowerCase()).join(", ")}
                  </p>
                )}
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
                  <p className="text-13 text-fg-muted">
                    {app.consent.status === "REVOKED" ? "Consent was revoked. No new data is pulled and stored copies were deleted." : "Checks run when data is pulled."}
                  </p>
                )}
                {app.consent.active && role === "rm" && (
                  <Button size="sm" variant="ghost" className="mt-4 text-danger" onClick={() => setRevoking(true)}>
                    Revoke on the MSME's request
                  </Button>
                )}
              </Card>
              <Card title="Peer comparison" description={app.peers ? `Compared with the typical result of ${app.peers.peer_count} factories in ${app.peers.cluster}` : undefined}>
                {app.peers?.rows.length ? (
                  <table className="w-full text-13">
                    <thead>
                      <tr className="text-left">
                        <th scope="col" className="label-caps pb-2">
                          Metric
                        </th>
                        <th scope="col" className="label-caps pb-2 text-right">
                          This unit
                        </th>
                        <th scope="col" className="label-caps pb-2 text-right">
                          Cluster
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {app.peers.rows.map((r) => (
                        <tr key={r.metric} className="border-t border-edge">
                          <th scope="row" className="py-2 pr-2 text-left font-normal text-fg">
                            {r.label}
                          </th>
                          <td className="tabular py-2 text-right font-semibold text-fg">{r.value}</td>
                          <td className="tabular py-2 pl-2 text-right text-fg-muted">{r.peer_median}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-13 text-fg-muted">Shows once consent is on.</p>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="memo">
          <MemoView
            applicationId={app.id}
            memo={app.memo}
            canGenerate={canMemo}
            generating={memo.isPending}
            onGenerate={() => memo.mutate()}
            generateHint={!sd ? "Score the application first. The memo is built from the score." : undefined}
            trace={app.memo ? <AgentTrace applicationId={app.id} memo={app.memo} canAudit={role === "risk"} /> : undefined}
          />
        </TabsContent>

        <TabsContent value="decision">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <MemoSummary app={app} onOpenPolicy={setPolicy} />
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

        <TabsContent value="activity">
          <Card title="Activity" description="Everything that happened on this application, newest first. “New” means it happened since you last looked.">
            {changes.isError ? <ErrorState error={changes.error} onRetry={() => changes.refetch()} /> : <WhatChanged items={changes.data} loading={changes.isLoading} />}
          </Card>
        </TabsContent>
      </Tabs>

      <PolicySheet section={policy} onClose={() => setPolicy(null)} />
      <Sheet open={whatIf} onOpenChange={setWhatIf} title="What-if simulator" description="Simulation only: it never changes the real score." className="max-w-2xl">
        {whatIf && <WhatIf applicationId={app.id} />}
      </Sheet>
      <Dialog
        open={revoking}
        onOpenChange={setRevoking}
        title="Revoke consent?"
        description="Do this only if the owner has asked for it."
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
