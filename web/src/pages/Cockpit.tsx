import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { CheckCheck, ChevronDown, FastForward, Play, ShieldCheck, ShieldOff, UserPlus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Badge, BandPill, Button, Card, DataTable, DropdownMenu, ErrorState, MenuItem, MenuLabel, SeverityPill, Skeleton, Stat, Tooltip } from "../components/ui";
import { AlertDrawer, RULE_LABEL } from "../features/cockpit/AlertDrawer";
import { Heatmap, type CellFilter } from "../features/cockpit/Heatmap";
import { MigrationMatrix } from "../features/cockpit/MigrationMatrix";
import { api, post } from "../lib/api";
import { runJob } from "../lib/jobs";
import { useAuth } from "../lib/auth";
import { cn } from "../lib/cn";
import { crore, inr, signed } from "../lib/format";
import { monthLabel } from "../lib/time";
import type { AdvanceResult, AlertRow, Migration, Portfolio, PortfolioAccount, StaffUser } from "../lib/types";

const SEV_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };
const STORY_WEEKS = 6;

function inCell<T extends { cluster: string; sector: string }>(rows: T[] | undefined, cell: CellFilter | null): T[] | undefined {
  return rows && cell ? rows.filter((r) => r.cluster === cell.cluster && r.sector === cell.sector) : rows;
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 60},${18 - ((v - min) / span) * 16}`).join(" ");
  const delta = values[values.length - 1] - values[0];
  return (
    <svg width={60} height={20} viewBox="0 0 60 20" role="img" aria-label={`Score over ${values.length} months: ${values[0]} to ${values[values.length - 1]}`}>
      <polyline points={pts} fill="none" stroke={delta < 0 ? "var(--danger)" : "var(--success)"} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function Cockpit() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const canAct = session!.role === "rm" || session!.role === "credit_officer";
  const [cell, setCell] = useState<CellFilter | null>(null);
  const [selected, setSelected] = useState<AlertRow[]>([]);
  const [showActioned, setShowActioned] = useState(false);
  const [story, setStory] = useState<{ week: number; newAlerts: number } | null>(null);
  const storyStop = useRef(false);

  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: () => api<Portfolio>("/portfolio") });
  const alerts = useQuery({ queryKey: ["alerts", showActioned], queryFn: () => api<AlertRow[]>(`/alerts?status=${showActioned ? "ALL" : "OPEN"}`) });
  const migration = useQuery({ queryKey: ["migration"], queryFn: () => api<Migration>("/portfolio/migration") });
  const staff = useQuery({ queryKey: ["staff"], queryFn: () => api<StaffUser[]>("/staff"), staleTime: Infinity, enabled: canAct });

  const refresh = () => Promise.all(["portfolio", "alerts", "migration", "clock", "palette"].map((k) => qc.invalidateQueries({ queryKey: [k] })));

  const [jobNote, setJobNote] = useState<string | null>(null);
  const advance = useMutation({
    mutationFn: (days: number) => runJob<AdvanceResult>(`/sim/advance?days=${days}`, (j) => setJobNote(j.message)),
    onSettled: () => setJobNote(null),
    onSuccess: async (r) => {
      await refresh();
      const blocked = r.blocked.length ? ` ${r.blocked.length} account(s) skipped: consent revoked.` : "";
      toast.success(`Clock moved to ${r.sim_date}. ${r.new_alerts.length} new alert${r.new_alerts.length === 1 ? "" : "s"}.${blocked}`);
    },
    onError: (e) => toast.error(`Could not move the clock: ${(e as Error).message}`),
  });

  async function playStory() {
    storyStop.current = false;
    let total = 0;
    setStory({ week: 0, newAlerts: 0 });
    try {
      for (let week = 1; week <= STORY_WEEKS && !storyStop.current; week++) {
        const r = await runJob<AdvanceResult>("/sim/advance?days=7");
        total += r.new_alerts.length;
        setStory({ week, newAlerts: total });
        await refresh();
        await new Promise((res) => setTimeout(res, 650));
      }
      toast.success(`Six weeks later: ${total} new alert${total === 1 ? "" : "s"} raised by the early-warning agent.`);
    } catch (e) {
      toast.error(`Story stopped: ${(e as Error).message}`);
    } finally {
      setStory(null);
    }
  }
  useEffect(
    () => () => {
      storyStop.current = true;
    },
    [],
  );

  const bulk = useMutation({
    mutationFn: (body: { action: "assign" | "acknowledge"; owner?: string }) => post<{ updated: number }>("/alerts/bulk", { ids: selected.map((a) => a.id), ...body }),
    onSuccess: async (r, body) => {
      await refresh();
      toast.success(
        body.action === "assign" ? `${r.updated} alert${r.updated === 1 ? "" : "s"} assigned to ${body.owner}` : `${r.updated} alert${r.updated === 1 ? "" : "s"} acknowledged`,
      );
    },
    onError: (e) => toast.error(`Bulk update failed: ${(e as Error).message}`),
  });

  const alertRows = useMemo(() => inCell(alerts.data, cell), [alerts.data, cell]);
  const accountRows = useMemo(() => inCell(portfolio.data?.accounts, cell), [portfolio.data, cell]);

  const openId = Number(params.get("alert"));
  const openAlert = useMemo(() => alerts.data?.find((a) => a.id === openId) ?? null, [alerts.data, openId]);
  const setOpen = (id: number | null) => setParams(id ? { alert: String(id) } : {}, { replace: true });

  const alertColumns = useMemo<ColumnDef<AlertRow>[]>(
    () => [
      {
        id: "severity",
        accessorFn: (a) => SEV_RANK[a.severity],
        header: "Severity",
        meta: { label: "Severity", csv: (a) => a.severity },
        cell: ({ row }) => <SeverityPill severity={row.original.severity} />,
      },
      {
        accessorKey: "name",
        header: "Factory",
        meta: { label: "Factory" },
        cell: ({ row: { original: a } }) => (
          <span>
            <span className="font-medium text-fg">{a.name}</span>
            <span className="ml-2 text-xs text-fg-muted">{a.cluster}</span>
          </span>
        ),
      },
      {
        id: "rules",
        accessorFn: (a) => a.rules.map((r) => RULE_LABEL[r] ?? r).join(", "),
        header: "Rule",
        meta: { label: "Rule" },
        enableSorting: false,
        cell: ({ getValue }) => <span className="text-fg-muted">{getValue<string>()}</span>,
      },
      { accessorKey: "days_open", header: "Days open", meta: { label: "Days open", align: "right" } },
      { accessorKey: "exposure", header: "Exposure", meta: { label: "Exposure (₹)", align: "right" }, cell: ({ getValue }) => inr(getValue<number>()) },
      {
        accessorKey: "owner",
        header: "Owner",
        meta: { label: "Owner" },
        cell: ({ row: { original: a } }) => (
          <span className="inline-flex items-center gap-1.5">
            {a.owner ?? <span className="text-fg-muted">Unassigned</span>}
            {a.acknowledged_by && (
              <Tooltip content={`Acknowledged by ${a.acknowledged_by}`}>
                <span tabIndex={0} aria-label={`Acknowledged by ${a.acknowledged_by}`}>
                  <CheckCheck className="h-3.5 w-3.5 text-info" aria-hidden />
                </span>
              </Tooltip>
            )}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        meta: { label: "Status" },
        cell: ({ row: { original: a } }) => (a.status === "ACTIONED" ? <Badge tone="success">Actioned: {a.action_taken}</Badge> : <Badge>Open</Badge>),
      },
    ],
    [],
  );

  const accountColumns = useMemo<ColumnDef<PortfolioAccount>[]>(
    () => [
      { accessorKey: "name", header: "Factory", meta: { label: "Factory" }, cell: ({ getValue }) => <span className="font-medium text-fg">{getValue<string>()}</span> },
      { accessorKey: "cluster", header: "Cluster", meta: { label: "Cluster" } },
      { accessorKey: "sector", header: "Sector", meta: { label: "Sector" } },
      { accessorKey: "exposure", header: "Exposure", meta: { label: "Exposure (₹)", align: "right" }, cell: ({ getValue }) => inr(getValue<number>()) },
      { accessorKey: "score", header: "Score", meta: { label: "Score", align: "right" }, cell: ({ getValue }) => <span className="font-semibold">{getValue<number>()}</span> },
      {
        accessorKey: "trend_3m",
        header: "3-month change",
        meta: { label: "3-month change", align: "right" },
        cell: ({ getValue }) => {
          const v = getValue<number>();
          return <span className={cn(v > 0 ? "text-success" : v < 0 ? "text-danger" : "text-fg-muted")}>{signed(v)}</span>;
        },
      },
      {
        id: "trend",
        header: "6 months",
        meta: { label: "6-month trend", csv: (a) => a.sparkline.join(" ") },
        enableSorting: false,
        cell: ({ row }) => <Sparkline values={row.original.sparkline} />,
      },
      { accessorKey: "band", header: "Band", meta: { label: "Band" }, cell: ({ row }) => <BandPill band={row.original.band} /> },
      {
        id: "alerts",
        accessorFn: (a) => SEV_RANK[a.max_severity ?? ""] ?? 0,
        header: "Alerts",
        meta: { label: "Highest open alert", csv: (a) => a.max_severity ?? "" },
        cell: ({ row }) => (row.original.max_severity ? <SeverityPill severity={row.original.max_severity} /> : <span className="text-fg-muted">–</span>),
      },
      {
        accessorKey: "consent_active",
        header: "Consent",
        meta: { label: "Consent", csv: (a) => (a.consent_active ? "active" : "revoked") },
        cell: ({ getValue }) =>
          getValue<boolean>() ? (
            <Badge tone="success" icon={<ShieldCheck className="h-3 w-3" aria-hidden />}>
              Active
            </Badge>
          ) : (
            <Badge tone="danger" icon={<ShieldOff className="h-3 w-3" aria-hidden />}>
              Revoked
            </Badge>
          ),
      },
    ],
    [],
  );

  if (portfolio.isError) return <ErrorState error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  const k = portfolio.data?.kpis;
  const flagged = portfolio.data ? portfolio.data.accounts.filter((a) => a.max_severity === "high" || a.max_severity === "medium") : [];
  const flaggedExposure = flagged.reduce((s, a) => s + a.exposure, 0);
  const busy = advance.isPending || story !== null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Portfolio risk cockpit</h1>
          <p className="mt-0.5 text-sm text-fg-muted">
            {portfolio.data ? `${portfolio.data.kpis.accounts} monitored accounts · data through ${monthLabel(portfolio.data.data_month)}` : "Loading the monitored portfolio…"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Simulated clock">
          <Button disabled={busy} loading={advance.isPending && advance.variables === 7} onClick={() => advance.mutate(7)} icon={<FastForward className="h-4 w-4" aria-hidden />}>
            +1 week
          </Button>
          <Button disabled={busy} loading={advance.isPending && advance.variables === 30} onClick={() => advance.mutate(30)} icon={<FastForward className="h-4 w-4" aria-hidden />}>
            +1 month
          </Button>
          <Button variant="primary" disabled={busy} onClick={playStory} icon={<Play className="h-4 w-4" aria-hidden />}>
            Play story
          </Button>
        </div>
      </div>

      {advance.isPending && jobNote && (
        <p role="status" className="text-13 text-fg-muted">
          Early-warning batch: {jobNote}
        </p>
      )}

      {story && (
        <div role="status" className="rounded-card border border-edge bg-primary-tint px-4 py-3">
          <div className="flex items-center justify-between gap-3 text-sm text-fg">
            <span>
              <span className="font-semibold">Playing six weeks: </span>
              week {story.week} of {STORY_WEEKS} · {story.newAlerts} new alert{story.newAlerts === 1 ? "" : "s"} so far
            </span>
            <Button size="sm" variant="ghost" onClick={() => (storyStop.current = true)}>
              Stop
            </Button>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-panel" aria-hidden>
            <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${(story.week / STORY_WEEKS) * 100}%` }} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Monitored accounts" value={k?.accounts ?? "–"} loading={portfolio.isLoading} />
        <Stat label="Total exposure" value={k ? `₹${crore(k.exposure)}` : "–"} loading={portfolio.isLoading} />
        <Stat label="Average score" value={k?.avg_score ?? "–"} sub="Factory Health Score, 300–900" loading={portfolio.isLoading} />
        <Stat
          label="Open alerts"
          loading={portfolio.isLoading}
          value={k ? k.alerts_by_severity.high + k.alerts_by_severity.medium + k.alerts_by_severity.low : "–"}
          sub={
            k && (
              <span className="flex flex-wrap gap-1 pt-0.5">
                {(["high", "medium", "low"] as const).map((s) => (
                  <span key={s} className="inline-flex items-center gap-1">
                    <SeverityPill severity={s} />
                    <span className="tabular font-semibold text-fg">{k.alerts_by_severity[s]}</span>
                  </span>
                ))}
              </span>
            )
          }
        />
        <Stat
          label="Exposure flagged early"
          loading={portfolio.isLoading}
          value={inr(flaggedExposure)}
          sub={
            k && (
              <Tooltip content={k.slippage_formula}>
                <span tabIndex={0} className="underline decoration-dotted underline-offset-2">
                  {flagged.length} account{flagged.length === 1 ? "" : "s"} with high or medium alerts · est. slippage avoided {inr(k.expected_slippage_avoided)}
                </span>
              </Tooltip>
            )
          }
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Card title="Cluster × sector heat-map" description="Select a cell to filter the alert queue and the accounts">
          {portfolio.data ? <Heatmap cells={portfolio.data.heatmap} selected={cell} onSelect={setCell} /> : <Skeleton className="h-72" />}
        </Card>
        <Card title="Score migration" description="Accounts that changed band since last month">
          {migration.isError ? (
            <ErrorState error={migration.error} onRetry={() => migration.refetch()} />
          ) : migration.data ? (
            <MigrationMatrix data={migration.data} />
          ) : (
            <Skeleton className="h-72" />
          )}
        </Card>
      </div>

      <Card title="Alert queue" description={cell ? `Filtered to ${cell.cluster} · ${cell.sector}` : "Raised by the early-warning agent, highest severity first"}>
        <DataTable
          caption="Early-warning alerts"
          data={alertRows}
          columns={alertColumns}
          getRowId={(a) => String(a.id)}
          loading={alerts.isLoading}
          error={alerts.error}
          onRetry={() => alerts.refetch()}
          initialSort={[{ id: "severity", desc: true }]}
          selectable={canAct}
          onSelectionChange={setSelected}
          onRowClick={(a) => setOpen(a.id)}
          rowLabel={(a) => `Open ${a.severity} alert for ${a.name}`}
          searchPlaceholder="Search alerts"
          csvName="alerts"
          maxHeight={420}
          emptyTitle="No open alerts"
          emptyDescription="Move the clock forward to let the early-warning agent scan new data."
          emptyAction={
            <Button variant="primary" disabled={busy} onClick={playStory} icon={<Play className="h-4 w-4" aria-hidden />}>
              Play story
            </Button>
          }
          toolbar={
            <>
              <DropdownMenu
                align="start"
                trigger={
                  <Button size="sm" disabled={!canAct || selected.length === 0 || bulk.isPending} icon={<UserPlus className="h-4 w-4" aria-hidden />}>
                    Assign {selected.length > 0 && `(${selected.length})`}
                    <ChevronDown className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                }
              >
                <MenuLabel>Assign to</MenuLabel>
                {(staff.data ?? []).map((u) => (
                  <MenuItem key={u.username} onSelect={() => bulk.mutate({ action: "assign", owner: u.username })}>
                    {u.display_name}
                  </MenuItem>
                ))}
              </DropdownMenu>
              <Button
                size="sm"
                disabled={!canAct || selected.length === 0 || bulk.isPending}
                onClick={() => bulk.mutate({ action: "acknowledge" })}
                icon={<CheckCheck className="h-4 w-4" aria-hidden />}
              >
                Acknowledge {selected.length > 0 && `(${selected.length})`}
              </Button>
              <label className="ml-1 inline-flex items-center gap-1.5 text-13 text-fg-muted">
                <input type="checkbox" className="h-4 w-4 accent-[var(--primary)]" checked={showActioned} onChange={(e) => setShowActioned(e.target.checked)} />
                Show actioned
              </label>
              {!canAct && <span className="text-xs text-fg-muted">Read-only for your role</span>}
            </>
          }
        />
      </Card>

      <Card title="Monitored accounts" description={cell ? `Filtered to ${cell.cluster} · ${cell.sector}` : undefined}>
        <DataTable
          caption="Monitored accounts"
          data={accountRows}
          columns={accountColumns}
          getRowId={(a) => String(a.application_id)}
          loading={portfolio.isLoading}
          onRowClick={(a) => nav(`/console/${a.application_id}`)}
          rowLabel={(a) => `Open account ${a.name}`}
          searchPlaceholder="Search accounts"
          csvName="monitored_accounts"
          maxHeight={520}
          emptyTitle="No monitored accounts"
          emptyDescription="Accounts appear here after disbursal."
        />
      </Card>

      <AlertDrawer alert={openAlert} canAct={canAct} onClose={() => setOpen(null)} onDone={refresh} />
    </div>
  );
}
