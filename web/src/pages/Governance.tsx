import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { Bot, CircleCheck, Cloud, HardDrive, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, ChartFrame, GRID, TOOLTIP } from "../components/charts";
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, Select, Skeleton, Stat, Tabs, TabsContent, TabsList, TabsTrigger, Timeline, type Tone } from "../components/ui";
import { COMPLIANCE } from "../features/governance/compliance";
import { api } from "../lib/api";
import { PILLAR_COLORS, pct } from "../lib/format";
import { dateTime } from "../lib/time";

interface Split {
  auc: number;
  ks: number;
  brier: number;
  n: number;
  positives: number;
  event_rate: number;
}
interface FairRow {
  group: string;
  n: number;
  default_rate: number;
  mean_score: number;
  approval_rate: number;
  auc: number | null;
  adverse_impact_ratio: number;
  equal_opportunity_ratio: number;
}
interface Model {
  name: string;
  type: string;
  owner: string;
  metrics: { train: Split; valid: Split; test: Split; band_default_rate_test: Record<string, number>; band_distribution_test: Record<string, number> } | null;
  fairness: { sector: FairRow[]; udyam_category: FairRow[] } | null;
  drift: { score_psi: number; features: Record<string, number>; status: string } | null;
  ews_backtest: {
    sma2_events_in_window: number;
    detected_30d_ahead: number;
    recall: number;
    median_lead_days: number;
    alerted_accounts: number;
    precision_sma2_within_6m: number;
    precision_true_stress: number;
  } | null;
  feature_importance: { feature: string; mean_abs_shap: number; pillar?: string }[] | null;
  model_card_md: string | null;
}
interface AuditRow {
  id: number;
  ts: string;
  user: string;
  role: string;
  agent: string;
  tool: string;
  action: string;
  application_id: number | null;
  inputs: Record<string, unknown> | null;
  output_hash: string | null;
}
interface LedgerEvent {
  id: number;
  ts: string;
  event: string;
  consent_id: string;
  factory_id: string;
  name: string;
  actor: string;
}
interface Usage {
  summary: {
    calls: number;
    by_provider: Record<string, number>;
    fallbacks: number;
    p50_latency_ms: number | null;
    p95_latency_ms: number | null;
    tokens_est: number;
    provider_in_use: string;
  };
  calls: {
    id: number;
    ts: string;
    agent: string;
    template_id: string;
    provider: string;
    location: "local" | "cloud";
    latency_ms: number;
    tokens_est: number;
    fallback: boolean;
    user: string;
    application_id: number | null;
  }[];
}

const FAIR_THRESHOLD = 0.8;
const PSI_WARN = 0.2;
const EVENT_TONE: Record<string, Tone> = { GRANTED: "success", DATA_PULL: "neutral", PULL_BLOCKED: "warning", REVOKED: "danger", DELETION_JOB: "info", EXPIRED: "warning" };

function PassFail({ ok, label }: { ok: boolean; label?: string }) {
  return ok ? (
    <Badge tone="success" icon={<CircleCheck className="h-3 w-3" aria-hidden />}>
      {label ?? "Pass"}
    </Badge>
  ) : (
    <Badge tone="danger" icon={<TriangleAlert className="h-3 w-3" aria-hidden />}>
      {label ?? "Fail"}
    </Badge>
  );
}

function FairnessTable({ title, rows }: { title: string; rows: FairRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-13">
        <caption className="pb-2 text-left text-13 font-semibold text-fg">{title}</caption>
        <thead>
          <tr className="text-xs text-fg-muted">
            {["Group", "Rows", "Default rate", "Approval rate", "AUC", "Adverse-impact ratio", "Equal-opportunity ratio", "Check"].map((h, i) => (
              <th key={h} scope="col" className={`border-b border-edge px-2 py-1.5 font-medium ${i === 0 || i === 7 ? "text-left" : "text-right"}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.group} className="border-b border-edge last:border-0">
              <th scope="row" className="px-2 py-1.5 text-left font-medium text-fg">
                {r.group.replace(/_/g, " ")}
              </th>
              <td className="px-2 py-1.5 text-right">{r.n.toLocaleString("en-IN")}</td>
              <td className="px-2 py-1.5 text-right">{pct(r.default_rate)}</td>
              <td className="px-2 py-1.5 text-right">{pct(r.approval_rate)}</td>
              <td className="px-2 py-1.5 text-right">{r.auc?.toFixed(2) ?? "–"}</td>
              <td className="px-2 py-1.5 text-right">{r.adverse_impact_ratio.toFixed(2)}</td>
              <td className="px-2 py-1.5 text-right">{r.equal_opportunity_ratio.toFixed(2)}</td>
              <td className="px-2 py-1.5">
                <PassFail ok={r.adverse_impact_ratio >= FAIR_THRESHOLD && r.equal_opportunity_ratio >= FAIR_THRESHOLD} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ModelTab() {
  const q = useQuery({ queryKey: ["model"], queryFn: () => api<Model>("/model"), staleTime: 60_000 });
  const [showCard, setShowCard] = useState(false);
  if (q.isLoading) return <Skeleton className="h-96" />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const m = q.data;
  const t = m.metrics?.test;
  const tr = m.metrics?.train;
  const top = (m.feature_importance ?? []).slice(0, 12).map((f) => ({ ...f, label: f.feature.replace(/_/g, " ") }));
  const drift = m.drift ? Object.entries(m.drift.features).sort((a, b) => b[1] - a[1]) : [];
  const worstPsi = m.drift ? Math.max(m.drift.score_psi, ...Object.values(m.drift.features)) : 0;

  return (
    <div className="space-y-5">
      <Card title={m.name} description={`${m.type} · owner: ${m.owner}`} actions={<Badge tone="info">Synthetic data</Badge>}>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat
            label="AUC, out-of-time test"
            value={t?.auc.toFixed(3) ?? "–"}
            sub={tr ? `train ${tr.auc.toFixed(3)} · ${t?.positives} defaults in ${t?.n.toLocaleString("en-IN")} rows` : undefined}
          />
          <Stat label="KS, out-of-time test" value={t?.ks.toFixed(3) ?? "–"} sub={tr ? `train ${tr.ks.toFixed(3)}` : undefined} />
          <Stat label="Brier score, test" value={t?.brier.toFixed(4) ?? "–"} sub="lower is better" />
          <Stat label="Event rate, test" value={pct(t?.event_rate, 2)} sub="defaults within 12 months" />
        </div>
        {tr && t && tr.auc - t.auc > 0.1 && (
          <p className="mt-4 flex items-start gap-2 rounded-control bg-warning-tint px-3 py-2 text-13 text-warning">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Train AUC is {(tr.auc - t.auc).toFixed(2)} above test AUC. The test figure is the honest one; the gap shows overfitting on a small synthetic panel.
          </p>
        )}
        <p className="mt-3 text-xs text-fg-muted">
          Time-based split: train months 4–12, validation 13–15, gap month 16, test months 17–24. A calibration curve and a challenger comparison are added with the model retrain.
        </p>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Feature importance" description="Mean absolute SHAP on the test set, top 12">
          {top.length ? (
            <ChartFrame
              height={340}
              label={`Top features by importance: ${top
                .slice(0, 5)
                .map((f) => f.label)
                .join(", ")}`}
            >
              <ResponsiveContainer>
                <BarChart data={top} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
                  <CartesianGrid {...GRID} horizontal={false} vertical />
                  <XAxis type="number" {...AXIS} />
                  <YAxis type="category" dataKey="label" {...AXIS} width={168} />
                  <Tooltip {...TOOLTIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => [v.toFixed(3), "Mean |SHAP|"]} />
                  <Bar dataKey="mean_abs_shap" radius={[0, 4, 4, 0]} barSize={14} isAnimationActive={false}>
                    {top.map((f) => (
                      <Cell key={f.feature} fill={(f.pillar && PILLAR_COLORS[f.pillar]) || "var(--chart-1)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartFrame>
          ) : (
            <EmptyState title="No importance report" description="Run the training pipeline to generate it." />
          )}
        </Card>

        <Card
          title="Drift"
          description="Population stability index, training months against test months"
          actions={m.drift && <PassFail ok={worstPsi <= PSI_WARN} label={worstPsi <= PSI_WARN ? `Stable · worst PSI ${worstPsi.toFixed(2)}` : `PSI above ${PSI_WARN}`} />}
        >
          {m.drift ? (
            <ul className="space-y-2">
              {[["score (overall)", m.drift.score_psi] as [string, number], ...drift].map(([name, v]) => (
                <li key={name} className="grid grid-cols-[minmax(0,1fr)_7rem_3.5rem] items-center gap-3 text-13">
                  <span className="truncate text-fg">{name.replace(/_/g, " ")}</span>
                  <span className="h-2 overflow-hidden rounded-full bg-panel-2" aria-hidden>
                    <span className={`block h-full rounded-full ${v > PSI_WARN ? "bg-danger" : "bg-chart-2"}`} style={{ width: `${Math.min(100, (v / 0.25) * 100)}%` }} />
                  </span>
                  <span className="tabular flex items-center justify-end gap-1 text-right font-medium text-fg">
                    {v > PSI_WARN && <TriangleAlert className="h-3.5 w-3.5 text-danger" aria-label="above warning threshold" />}
                    {v.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No drift report" />
          )}
          <p className="mt-3 text-xs text-fg-muted">A warning shows when PSI is above {PSI_WARN}.</p>
        </Card>
      </div>

      {m.fairness && (
        <Card
          title="Fairness"
          description={`Pass when both ratios are at least ${FAIR_THRESHOLD} of the best group (four-fifths rule). No protected attributes are used; sector and size are monitored only.`}
        >
          <div className="space-y-6">
            <FairnessTable title="By sector" rows={m.fairness.sector} />
            <FairnessTable title="By enterprise size" rows={m.fairness.udyam_category} />
          </div>
        </Card>
      )}

      {m.ews_backtest && (
        <Card title="Early-warning back-test" description="Alerts against accounts that later reached SMA-2">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Median lead time" value={`${Math.round(m.ews_backtest.median_lead_days)} days`} sub="first alert before SMA-2" />
            <Stat
              label="Detected 30+ days ahead"
              value={`${m.ews_backtest.detected_30d_ahead} of ${m.ews_backtest.sma2_events_in_window}`}
              sub="SMA-2 events in the window (a small sample)"
            />
            <Stat
              label="Precision"
              value={pct(m.ews_backtest.precision_sma2_within_6m, 0)}
              sub={`of ${m.ews_backtest.alerted_accounts} alerted accounts reached SMA-2 in 6 months`}
            />
            <Stat label="Precision, any real stress" value={pct(m.ews_backtest.precision_true_stress, 0)} sub="alerted accounts that were genuinely stressed" />
          </div>
        </Card>
      )}

      {m.model_card_md && (
        <Card
          title="Model card"
          actions={
            <Button size="sm" onClick={() => setShowCard(!showCard)} aria-expanded={showCard}>
              {showCard ? "Hide" : "Show full card"}
            </Button>
          }
        >
          {showCard ? (
            <pre className="max-h-[32rem] overflow-auto rounded-control bg-panel-2 p-4 text-xs leading-relaxed whitespace-pre-wrap text-fg">{m.model_card_md}</pre>
          ) : (
            <p className="text-13 text-fg-muted">Intended use, data, performance, fairness, limitations.</p>
          )}
        </Card>
      )}
    </div>
  );
}

function AuditTab() {
  const q = useQuery({ queryKey: ["audit"], queryFn: () => api<AuditRow[]>("/audit?limit=500") });
  const [agent, setAgent] = useState("");
  const [user, setUser] = useState("");
  const [shown, setShown] = useState(40);
  const agents = useMemo(() => [...new Set((q.data ?? []).map((r) => r.agent))].sort(), [q.data]);
  const users = useMemo(() => [...new Set((q.data ?? []).map((r) => r.user))].sort(), [q.data]);
  const rows = useMemo(() => (q.data ?? []).filter((r) => (!agent || r.agent === agent) && (!user || r.user === user)), [q.data, agent, user]);

  if (q.isLoading) return <Skeleton className="h-96" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return (
    <Card title="Audit trail" description="Every API action and agent tool call, newest first. Inputs are PII-masked; outputs are stored as a SHA-256 hash.">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-fg-muted">
          Agent
          <Select className="mt-1 w-52" value={agent} onChange={(e) => (setAgent(e.target.value), setShown(40))}>
            <option value="">All agents</option>
            {agents.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </Select>
        </label>
        <label className="text-xs font-medium text-fg-muted">
          User
          <Select className="mt-1 w-40" value={user} onChange={(e) => (setUser(e.target.value), setShown(40))}>
            <option value="">All users</option>
            {users.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </Select>
        </label>
        <p className="tabular ml-auto text-xs text-fg-muted" aria-live="polite">
          {rows.length} entries
        </p>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No audit entries" description="Nothing matches these filters." action={<Button onClick={() => (setAgent(""), setUser(""))}>Clear filters</Button>} />
      ) : (
        <>
          <Timeline
            items={rows.slice(0, shown).map((r) => ({
              id: r.id,
              tone: r.agent === "api" ? "neutral" : "primary",
              icon: r.agent === "api" ? undefined : <Bot className="h-3.5 w-3.5" />,
              title: (
                <span>
                  {r.agent} · {r.tool} <span className="font-normal text-fg-muted">· {r.action}</span>
                </span>
              ),
              meta: dateTime(r.ts),
              body: (
                <span className="tabular">
                  #{r.id} · {r.user} ({r.role}){r.application_id != null && ` · application #${r.application_id}`}
                  {r.output_hash && <> · output sha256 {r.output_hash.slice(0, 12)}…</>}
                </span>
              ),
            }))}
          />
          {rows.length > shown && (
            <Button className="mt-4" onClick={() => setShown(shown + 60)}>
              Show more ({rows.length - shown} left)
            </Button>
          )}
        </>
      )}
    </Card>
  );
}

function LedgerTab() {
  const q = useQuery({ queryKey: ["consent-ledger"], queryFn: () => api<{ consents: Record<string, number>; events: LedgerEvent[] }>("/consent-ledger?limit=1000") });
  const columns = useMemo<ColumnDef<LedgerEvent>[]>(
    () => [
      { accessorKey: "ts", header: "When", meta: { label: "When" }, cell: ({ getValue }) => <span className="tabular text-fg-muted">{dateTime(getValue<string>())}</span> },
      {
        accessorKey: "event",
        header: "Event",
        meta: { label: "Event" },
        cell: ({ getValue }) => <Badge tone={EVENT_TONE[getValue<string>()] ?? "neutral"}>{getValue<string>().replace(/_/g, " ").toLowerCase()}</Badge>,
      },
      { accessorKey: "name", header: "Factory", meta: { label: "Factory" }, cell: ({ getValue }) => <span className="font-medium text-fg">{getValue<string>()}</span> },
      {
        accessorKey: "consent_id",
        header: "Consent",
        meta: { label: "Consent id" },
        cell: ({ getValue }) => <span className="tabular text-xs text-fg-muted">{getValue<string>()}</span>,
      },
      { accessorKey: "actor", header: "Actor", meta: { label: "Actor" } },
    ],
    [],
  );
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Active consents" value={q.data?.consents.ACTIVE ?? "–"} loading={q.isLoading} />
        <Stat label="Revoked" value={q.data?.consents.REVOKED ?? "–"} loading={q.isLoading} />
        <Stat label="Expired" value={q.data?.consents.EXPIRED ?? "–"} loading={q.isLoading} />
      </div>
      <Card title="Consent ledger" description="Append-only record of grants, data pulls, blocked pulls, expiries, revocations and deletion jobs">
        <DataTable
          caption="Consent ledger events"
          data={q.data?.events}
          columns={columns}
          getRowId={(e) => String(e.id)}
          loading={q.isLoading}
          error={q.error}
          onRetry={() => q.refetch()}
          searchPlaceholder="Search the ledger"
          csvName="consent_ledger"
          emptyTitle="No consent events yet"
        />
      </Card>
    </div>
  );
}

function UsageTab() {
  const q = useQuery({ queryKey: ["ai-usage"], queryFn: () => api<Usage>("/ai-usage?limit=1000") });
  const s = q.data?.summary;
  const columns = useMemo<ColumnDef<Usage["calls"][number]>[]>(
    () => [
      { accessorKey: "ts", header: "When", meta: { label: "When" }, cell: ({ getValue }) => <span className="tabular text-fg-muted">{dateTime(getValue<string>())}</span> },
      { accessorKey: "agent", header: "Agent", meta: { label: "Agent" } },
      {
        accessorKey: "template_id",
        header: "Prompt template",
        meta: { label: "Prompt template" },
        cell: ({ getValue }) => <code className="text-xs text-fg">{getValue<string>()}</code>,
      },
      {
        accessorKey: "provider",
        header: "Provider",
        meta: { label: "Provider" },
        cell: ({ row: { original: c } }) => (
          <Badge
            tone={c.location === "local" ? "success" : "info"}
            icon={c.location === "local" ? <HardDrive className="h-3 w-3" aria-hidden /> : <Cloud className="h-3 w-3" aria-hidden />}
          >
            {c.provider} · {c.location}
          </Badge>
        ),
      },
      { accessorKey: "latency_ms", header: "Latency", meta: { label: "Latency (ms)", align: "right" }, cell: ({ getValue }) => `${getValue<number>().toFixed(1)} ms` },
      {
        accessorKey: "tokens_est",
        header: "Tokens (est.)",
        meta: { label: "Tokens (estimate)", align: "right" },
        cell: ({ getValue }) => getValue<number>().toLocaleString("en-IN"),
      },
      {
        accessorKey: "fallback",
        header: "Fallback",
        meta: { label: "Fallback", csv: (c) => (c.fallback ? "yes" : "no") },
        cell: ({ getValue }) => (getValue<boolean>() ? <Badge tone="warning">Template fallback</Badge> : <span className="text-fg-muted">–</span>),
      },
      {
        accessorKey: "application_id",
        header: "Application",
        meta: { label: "Application", align: "right" },
        cell: ({ getValue }) => (getValue<number | null>() != null ? `#${getValue<number>()}` : "–"),
      },
    ],
    [],
  );
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Writer calls" value={s?.calls.toLocaleString("en-IN") ?? "–"} sub={s ? `provider in use: ${s.provider_in_use}` : undefined} loading={q.isLoading} />
        <Stat label="Latency, p50 / p95" value={s?.p50_latency_ms != null ? `${s.p50_latency_ms.toFixed(1)} / ${s.p95_latency_ms?.toFixed(1)} ms` : "–"} loading={q.isLoading} />
        <Stat label="Fallbacks to template" value={s?.fallbacks ?? "–"} sub="provider failed or the number guard rejected the text" loading={q.isLoading} />
        <Stat label="Tokens (estimate)" value={s?.tokens_est.toLocaleString("en-IN") ?? "–"} sub="characters ÷ 4, not billed tokens" loading={q.isLoading} />
      </div>
      <Card title="AI usage log" description="Each writer call by an agent. The LLM writes prose only; it never produces numbers.">
        <DataTable
          caption="AI usage log"
          data={q.data?.calls}
          columns={columns}
          getRowId={(c) => String(c.id)}
          loading={q.isLoading}
          error={q.error}
          onRetry={() => q.refetch()}
          searchPlaceholder="Search calls"
          csvName="ai_usage"
          emptyTitle="No AI calls yet"
          emptyDescription="Calls appear when a memo, a briefing or a plan is written."
        />
      </Card>
    </div>
  );
}

const STATUS: Record<string, { tone: Tone; label: string }> = {
  implemented: { tone: "success", label: "Implemented" },
  stub: { tone: "warning", label: "Prototype stub" },
  production: { tone: "info", label: "Production only" },
};

function ComplianceTab() {
  return (
    <div className="space-y-5">
      <p className="rounded-control bg-info-tint px-3 py-2 text-13 text-info">
        Prototype status: controls run against synthetic data. A production deployment needs the lender's legal review, a data-protection impact assessment and independent model
        validation.
      </p>
      {COMPLIANCE.map((f) => (
        <Card key={f.framework} title={f.framework} description={f.note}>
          <ul className="divide-y divide-edge">
            {f.controls.map((c) => (
              <li key={c.expectation} className="grid gap-x-4 gap-y-1 py-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)_auto]">
                <p className="text-13 font-medium text-fg">{c.expectation}</p>
                <div>
                  <p className="text-13 text-fg">{c.control}</p>
                  <p className="mt-0.5 text-xs text-fg-muted">Evidence: {c.evidence}</p>
                </div>
                <div>
                  <Badge tone={STATUS[c.status].tone}>{STATUS[c.status].label}</Badge>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}

export default function Governance() {
  const [tab, setTab] = useState("model");
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Governance and compliance</h1>
        <p className="mt-0.5 text-sm text-fg-muted">Model inventory, audit trail, consent ledger, AI usage and regulatory mapping.</p>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="audit">Audit trail</TabsTrigger>
          <TabsTrigger value="consent">Consent ledger</TabsTrigger>
          <TabsTrigger value="ai">AI usage</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
        </TabsList>
        <TabsContent value="model">
          <ModelTab />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTab />
        </TabsContent>
        <TabsContent value="consent">
          <LedgerTab />
        </TabsContent>
        <TabsContent value="ai">
          <UsageTab />
        </TabsContent>
        <TabsContent value="compliance">
          <ComplianceTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
