import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { FilePlus2, Flag, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Badge, BandPill, Button, Card, DataTable, Dialog, EmptyState, Field, Input, SkeletonRows, Stat } from "../components/ui";
import { api, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn } from "../lib/cn";
import { inr, pct } from "../lib/format";
import { ago, STATE_LABEL } from "../lib/time";
import type { AppStats, AppSummary, FactoryHit } from "../lib/types";

type FilterKey = "queue" | "decision" | "watch" | "all";
const FILTERS: { key: FilterKey; label: string; test: (a: AppSummary) => boolean }[] = [
  { key: "queue", label: "My queue", test: (a) => a.decision === null },
  { key: "decision", label: "Needs decision", test: (a) => a.state === "MEMO_DRAFTED" },
  { key: "watch", label: "Watch band", test: (a) => a.band === "WATCH" },
  { key: "all", label: "All", test: () => true },
];

function NewApplication({ open, onOpenChange, initial }: { open: boolean; onOpenChange: (o: boolean) => void; initial: string }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [q, setQ] = useState(initial);
  useEffect(() => {
    if (open) setQ(initial);
  }, [open, initial]);
  const term = q.trim();
  const hits = useQuery({ queryKey: ["factories", term], queryFn: () => api<FactoryHit[]>(`/factories?q=${encodeURIComponent(term)}&limit=8`), enabled: open && term.length >= 2 });
  const create = useMutation({
    mutationFn: (factory_id: string) => post<AppSummary>("/applications", { factory_id, channel: "rm" }),
    onSuccess: (a) => {
      toast.success(`Application #${a.id} created for ${a.name}`);
      void qc.invalidateQueries({ queryKey: ["applications"] });
      onOpenChange(false);
      nav(`/console/${a.id}`);
    },
    onError: (e) => toast.error(`Could not create the application: ${(e as Error).message}`),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="New application" description="Find a factory by name or ID. The requested amount comes from its profile.">
      <Field label="Factory" hint="Type at least two characters, for example “Ceramics” or “UP-F0042”.">
        <Input value={q} onChange={(e) => setQ(e.target.value)} autoFocus placeholder="Search factories" />
      </Field>
      <div className="mt-3 min-h-40">
        {term.length < 2 ? null : hits.isLoading ? (
          <SkeletonRows rows={3} />
        ) : hits.isError ? (
          <p className="text-sm text-danger">Search failed: {(hits.error as Error).message}</p>
        ) : !hits.data?.length ? (
          <EmptyState title="No factory found" description={`Nothing matches “${term}”.`} className="py-6" />
        ) : (
          <ul className="divide-y divide-edge">
            {hits.data.map((f) => (
              <li key={f.factory_id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-fg">{f.name}</p>
                  <p className="truncate text-xs text-fg-muted">
                    {f.factory_id} · {f.sector_label} · {f.cluster} · {f.udyam_category} · {f.turnover_band}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="primary"
                  loading={create.isPending && create.variables === f.factory_id}
                  disabled={create.isPending}
                  onClick={() => create.mutate(f.factory_id)}
                >
                  Create · {inr(f.loan_requested_inr)}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}

export default function Console() {
  const { session } = useAuth();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<FilterKey>(() => (localStorage.getItem("up_console_filter") as FilterKey) || "queue");
  const factoryParam = params.get("factory") ?? "";
  const [creating, setCreating] = useState(false);
  const canCreate = session?.role === "rm";

  useEffect(() => {
    if (factoryParam && canCreate) setCreating(true);
  }, [factoryParam, canCreate]);

  const apps = useQuery({ queryKey: ["applications"], queryFn: () => api<AppSummary[]>("/applications") });
  const stats = useQuery({ queryKey: ["applications", "stats"], queryFn: () => api<AppStats>("/applications/stats") });

  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f.key, (apps.data ?? []).filter(f.test).length])) as Record<FilterKey, number>, [apps.data]);
  const rows = useMemo(() => (apps.data ?? []).filter(FILTERS.find((f) => f.key === filter)!.test), [apps.data, filter]);

  const columns = useMemo<ColumnDef<AppSummary>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Factory",
        meta: { label: "Factory" },
        cell: ({ row: { original: a } }) => (
          <span className="flex items-center gap-2">
            <span className="font-medium text-fg">{a.name}</span>
            <span className="tabular text-xs text-fg-muted">#{a.id}</span>
            {a.review_requested && (
              <Badge tone="warning" icon={<Flag className="h-3 w-3" aria-hidden />}>
                Review requested
              </Badge>
            )}
          </span>
        ),
      },
      { accessorKey: "cluster", header: "Cluster", meta: { label: "Cluster" } },
      { accessorKey: "sector", header: "Sector", meta: { label: "Sector" } },
      { accessorKey: "requested_amount", header: "Requested", meta: { label: "Requested (₹)", align: "right" }, cell: ({ getValue }) => inr(getValue<number>()) },
      {
        accessorKey: "score",
        header: "Score",
        meta: { label: "Score", align: "right", csv: (a) => a.score },
        sortUndefined: "last",
        cell: ({ row: { original: a } }) =>
          a.score == null ? (
            <span className="text-fg-muted">–</span>
          ) : (
            <span className="inline-flex items-center justify-end gap-2">
              <span className="font-semibold">{a.score}</span>
              <BandPill band={a.band} />
            </span>
          ),
      },
      {
        accessorKey: "state",
        header: "State",
        meta: { label: "State" },
        cell: ({ row: { original: a } }) => (
          <Badge tone={a.decision === "REJECTED" ? "danger" : a.decision === "APPROVED" ? "success" : "neutral"}>
            {a.decision === "REJECTED" ? "Rejected" : STATE_LABEL[a.state]}
          </Badge>
        ),
      },
      {
        accessorKey: "last_activity",
        header: "Last activity",
        meta: { label: "Last activity", csv: (a) => a.last_activity },
        cell: ({ getValue }) => <span className="text-fg-muted">{ago(getValue<string | null>())}</span>,
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Applications</h1>
          <p className="mt-0.5 text-sm text-fg-muted">Underwrite MSME manufacturers on consented GST, e-way bill, bank, power and payroll data.</p>
        </div>
        {canCreate && (
          <Button variant="primary" onClick={() => setCreating(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
            New application
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Pending" value={stats.data?.pending ?? "–"} sub={stats.data ? `${stats.data.needs_decision} waiting for a decision` : undefined} loading={stats.isLoading} />
        <Stat label="Scored today" value={stats.data?.scored_today ?? "–"} sub="applications scored since midnight" loading={stats.isLoading} />
        <Stat
          label="Average decision time"
          value={
            stats.data?.avg_decision_hours == null
              ? "–"
              : stats.data.avg_decision_hours < 1
                ? `${Math.round(stats.data.avg_decision_hours * 60)} min`
                : `${stats.data.avg_decision_hours.toFixed(1)} h`
          }
          sub={stats.data?.decisions ? `from application to decision, ${stats.data.decisions} decided here` : "no decisions made here yet"}
          loading={stats.isLoading}
        />
        <Stat
          label="Approval rate"
          value={pct(stats.data?.approval_rate, 0)}
          sub={stats.data?.decisions ? `of ${stats.data.decisions} decisions made here` : "no decisions made here yet"}
          loading={stats.isLoading}
        />
      </div>

      <Card>
        <DataTable
          caption="Loan applications"
          data={apps.data ? rows : undefined}
          columns={columns}
          getRowId={(a) => String(a.id)}
          loading={apps.isLoading}
          error={apps.error}
          onRetry={() => apps.refetch()}
          onRowClick={(a) => nav(`/console/${a.id}`)}
          rowLabel={(a) => `Open application ${a.id}, ${a.name}`}
          searchPlaceholder="Search applications"
          csvName="applications"
          emptyTitle={filter === "all" ? "No applications yet" : "Nothing in this view"}
          emptyDescription={filter === "all" ? "Create the first application to start underwriting." : "Try another saved filter."}
          emptyAction={
            filter !== "all" ? (
              <Button onClick={() => setFilter("all")}>Show all applications</Button>
            ) : canCreate ? (
              <Button variant="primary" onClick={() => setCreating(true)} icon={<FilePlus2 className="h-4 w-4" aria-hidden />}>
                New application
              </Button>
            ) : undefined
          }
          toolbar={
            <div role="tablist" aria-label="Saved filters" className="flex gap-1 rounded-control bg-panel-2 p-1">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  role="tab"
                  type="button"
                  aria-selected={filter === f.key}
                  onClick={() => {
                    localStorage.setItem("up_console_filter", f.key);
                    setFilter(f.key);
                  }}
                  className={cn("rounded-md px-2.5 py-1 text-13 font-medium transition-colors", filter === f.key ? "bg-panel text-fg shadow-card" : "text-fg-muted hover:text-fg")}
                >
                  {f.label}
                  <span className="tabular ml-1.5 text-xs text-fg-muted">{counts[f.key] ?? 0}</span>
                </button>
              ))}
            </div>
          }
        />
      </Card>

      <NewApplication
        open={creating}
        initial={factoryParam}
        onOpenChange={(o) => {
          setCreating(o);
          if (!o && factoryParam) setParams({}, { replace: true });
        }}
      />
    </div>
  );
}
