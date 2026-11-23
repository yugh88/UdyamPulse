import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Flag, Plus, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { ChangeBadge, ChangedBar, ChangedHint, Delta } from "../components/change";
import {
  Badge,
  BandPill,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  Select,
  Sheet,
  SkeletonRows,
  Stat,
  TabCount,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  useUrlTab,
} from "../components/ui";
import { api, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useMarkSeen } from "../lib/changes";
import { cn } from "../lib/cn";
import { BAND_LABEL, inr, pct, type Band } from "../lib/format";
import type { AppStats, AppSummary, FactoryHit, Tile } from "../lib/types";

const TABS = ["action", "progress", "decided"] as const;
type TabKey = (typeof TABS)[number];
const TAB_LABEL: Record<TabKey, string> = { action: "Needs your action", progress: "In progress", decided: "Decided" };

function tabOf(a: AppSummary): TabKey {
  if (a.decision) return "decided";
  return a.next_step?.yours ? "action" : "progress";
}

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
    <Dialog open={open} onOpenChange={onOpenChange} title="New application" description="Search for a factory by name or ID. The amount it asked for is filled in for you.">
      <Field label="Factory" hint="Type 2 or more characters, for example “Ceramics” or “UP-F0042”.">
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

/**
 * The next step in plain words, coloured by what it asks: purple = AI work is ready for you to review, ochre =
 * something got worse. Everything else (your manual steps and waiting states) is a neutral grey pill; your own
 * steps are bold.
 */
function NextStep({ a }: { a: AppSummary }) {
  if (a.score_delta != null && a.score_delta < 0 && !a.decision)
    return (
      <Badge tone="warning" className="font-semibold">
        Score dropped: check reasons
      </Badge>
    );
  if (!a.next_step) return <span className="text-13 text-fg-muted">–</span>;
  const ai = a.state === "MEMO_DRAFTED" || a.state === "SCORED";
  return (
    <Badge tone={a.next_step.yours && ai ? "purple" : "neutral"} className={cn(a.next_step.yours && "font-semibold text-fg")}>
      {a.next_step.text}
    </Badge>
  );
}

/** Score, band and how much it moved: since the user last looked when it was re-scored, else since last month. */
function ScoreCell({ a }: { a: AppSummary }) {
  if (a.score == null) return <span className="text-sm text-fg-muted">Not scored yet</span>;
  const rescored = a.changed_since_seen && a.score_delta ? a.score_delta : null;
  const delta = rescored ?? (a.score_trend?.delta || null);
  return (
    <span className="flex flex-wrap items-center gap-2.5">
      <span className="tabular text-lg font-bold text-fg">{a.score}</span>
      <BandPill band={a.band} />
      {delta ? (
        <span title={rescored ? "Change since you last looked" : `Change since ${a.score_trend?.since}`}>
          <Delta value={delta} goodWhenUp />
        </span>
      ) : null}
    </span>
  );
}

function hoursLabel(h: number | null): string {
  if (h == null) return "–";
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`;
  if (h < 48) return `${h.toFixed(1)} h`;
  return `${(h / 24).toFixed(1)} days`;
}

function Tiles({ tiles, loading }: { tiles?: AppStats["tiles"]; loading: boolean }) {
  const w = tiles?.waiting_on_you;
  const m = tiles?.avg_hours_to_memo;
  const r = tiles?.approval_rate_30d;
  const delta = (t: Tile | undefined, unit: string, suffix?: string) =>
    t && t.delta != null ? <Delta value={t.delta} before={t.prev_value} after={t.value} unit={unit} goodWhenUp={t.good_when_up} suffix={suffix} /> : null;
  return (
    <div className="grid gap-5 md:grid-cols-3">
      <Stat label="Waiting on you" loading={loading} value={w?.value ?? "–"} delta={delta(w, "", w?.period)} />
      <Stat
        label="Avg. time to memo"
        loading={loading}
        value={hoursLabel(m?.value ?? null)}
        delta={m?.value != null ? delta(m, "hours") : null}
        sub={m?.value == null ? "no memos in the last 30 days" : "application to memo, last 30 days"}
      />
      <Stat
        label="Approval rate · 30 days"
        loading={loading}
        value={r?.value == null ? "–" : pct(r.value, 0)}
        delta={delta(r, "pts")}
        sub={r?.value == null ? "no decisions in the last 30 days" : undefined}
      />
    </div>
  );
}

interface Filters {
  q: string;
  band: "" | Band;
  cluster: string;
}

export default function Console() {
  const { session } = useAuth();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useUrlTab(TABS, "action");
  const [filters, setFilters] = useState<Filters>({ q: "", band: "", cluster: "" });
  const [filtering, setFiltering] = useState(false);
  const factoryParam = params.get("factory") ?? "";
  const [creating, setCreating] = useState(false);
  const canCreate = session?.role === "rm";
  const seen = useMarkSeen();

  useEffect(() => {
    if (factoryParam && canCreate) setCreating(true);
  }, [factoryParam, canCreate]);

  const apps = useQuery({ queryKey: ["applications"], queryFn: () => api<AppSummary[]>("/applications") });
  const stats = useQuery({ queryKey: ["applications", "stats"], queryFn: () => api<AppStats>("/applications/stats") });

  const filtered = useMemo(() => {
    const q = filters.q.trim().toLowerCase();
    return (apps.data ?? []).filter(
      (a) =>
        (!q || `${a.name} ${a.factory_id} ${a.id}`.toLowerCase().includes(q)) && (!filters.band || a.band === filters.band) && (!filters.cluster || a.cluster === filters.cluster),
    );
  }, [apps.data, filters]);
  const counts = useMemo(() => {
    const c: Record<TabKey, number> = { action: 0, progress: 0, decided: 0 };
    filtered.forEach((a) => c[tabOf(a)]++);
    return c;
  }, [filtered]);
  // Changed items first, then the oldest application: the queue is worked from the top.
  const rows = useMemo(() => filtered.filter((a) => tabOf(a) === tab).sort((x, y) => Number(!!y.changed_since_seen) - Number(!!x.changed_since_seen)), [filtered, tab]);
  const clusters = useMemo(() => [...new Set((apps.data ?? []).map((a) => a.cluster))].sort(), [apps.data]);
  const active = Number(!!filters.q) + Number(!!filters.band) + Number(!!filters.cluster);
  const unseen = (apps.data ?? []).filter((a) => a.changed_since_seen);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Applications"
        description="Loan applications from factories in your branch."
        actions={
          canCreate && (
            <Button variant="primary" size="lg" onClick={() => setCreating(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
              New application
            </Button>
          )
        }
      />

      <Tabs value={tab} onValueChange={setTab}>
        <div className="flex items-end justify-between gap-4 border-b border-edge">
          <TabsList className="border-b-0" aria-label="Application queues">
            {TABS.map((k) => (
              <TabsTrigger key={k} value={k}>
                {TAB_LABEL[k]}
                <TabCount value={apps.data ? counts[k] : null} />
              </TabsTrigger>
            ))}
          </TabsList>
          <Button size="sm" variant="ghost" className="mb-1.5" onClick={() => setFiltering(true)} icon={<SlidersHorizontal className="h-4 w-4" aria-hidden />}>
            Filter{active ? ` (${active})` : ""}
          </Button>
        </div>
        <TabsContent value={tab} className="space-y-6 pt-6">
          <Tiles tiles={stats.data?.tiles} loading={stats.isLoading} />

          <Card padded={false} className="overflow-hidden">
            {apps.isLoading ? (
              <div className="p-6">
                <SkeletonRows rows={5} />
              </div>
            ) : apps.isError ? (
              <ErrorState error={apps.error} onRetry={() => apps.refetch()} />
            ) : rows.length === 0 ? (
              <EmptyState
                title={tab === "action" ? "Nothing needs your action" : tab === "decided" ? "No decisions yet" : "Nothing in progress"}
                description={
                  active
                    ? "No application matches these filters."
                    : tab === "action"
                      ? "You are all caught up. New work will show here."
                      : "Applications show here once they start moving forward."
                }
                action={
                  active ? (
                    <Button onClick={() => setFilters({ q: "", band: "", cluster: "" })}>Clear filters</Button>
                  ) : canCreate && tab === "action" ? (
                    <Button variant="primary" onClick={() => setCreating(true)} icon={<Plus className="h-4 w-4" aria-hidden />}>
                      New application
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <>
                {/* Phones: one card per application, so every field (including the next step) is readable. */}
                <ul className="divide-y divide-edge md:hidden" aria-label={`${TAB_LABEL[tab]}: loan applications`}>
                  {rows.map((a) => (
                    <li key={a.id} className="relative">
                      <button
                        type="button"
                        onClick={() => nav(`/console/${a.id}`)}
                        aria-label={`Open application ${a.id}, ${a.name}${a.changed_since_seen ? ", changed since you last looked" : ""}`}
                        className="flex w-full items-start gap-3 px-5 py-4 text-left transition-colors hover:bg-panel-2/60"
                      >
                        <ChangedBar show={a.changed_since_seen} className="inset-y-1" />
                        <span className="min-w-0 flex-1 space-y-2">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="text-base font-semibold text-fg">{a.name}</span>
                            <ChangeBadge kind={a.changed_since_seen ? a.change_kind : null} />
                          </span>
                          <span className="block text-sm text-fg-muted">
                            {a.cluster} · {a.sector} · <span className="tabular font-semibold text-fg">{inr(a.requested_amount)}</span>
                          </span>
                          <span className="block">
                            <ScoreCell a={a} />
                          </span>
                          <span className="block">
                            <NextStep a={a} />
                          </span>
                        </span>
                        <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-fg-subtle" aria-hidden />
                      </button>
                    </li>
                  ))}
                </ul>
                <table className="hidden w-full text-left md:table">
                  <caption className="sr-only">{TAB_LABEL[tab]}: loan applications</caption>
                  <thead className="bg-panel-2">
                    <tr>
                      <th scope="col" className="label-caps py-3.5 pr-4 pl-8 font-semibold">
                        Factory
                      </th>
                      <th scope="col" className="label-caps px-4 py-3.5 font-semibold">
                        Amount
                      </th>
                      <th scope="col" className="label-caps px-4 py-3.5 font-semibold">
                        Health score
                      </th>
                      <th scope="col" className="label-caps hidden px-4 py-3.5 font-semibold lg:table-cell">
                        Next step
                      </th>
                      <th scope="col" className="w-12">
                        <span className="sr-only">Open</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-edge">
                    {rows.map((a) => (
                      <tr
                        key={a.id}
                        tabIndex={0}
                        aria-label={`Open application ${a.id}, ${a.name}${a.changed_since_seen ? ", changed since you last looked" : ""}`}
                        onClick={() => nav(`/console/${a.id}`)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            nav(`/console/${a.id}`);
                          }
                        }}
                        className="group relative cursor-pointer transition-colors duration-150 hover:bg-panel-2/60 focus-visible:bg-panel-2/60"
                      >
                        <td className="relative py-4 pr-4 pl-8">
                          <ChangedBar show={a.changed_since_seen} className="inset-y-1" />
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-base font-semibold text-fg">{a.name}</span>
                            <ChangeBadge kind={a.changed_since_seen ? a.change_kind : null} />
                            {a.review_requested && (
                              <Badge tone="warning" icon={<Flag className="h-3 w-3" aria-hidden />}>
                                Review requested
                              </Badge>
                            )}
                          </div>
                          <p className="mt-0.5 text-sm text-fg-muted">
                            {a.cluster} · {a.sector}
                          </p>
                          <div className="mt-2 lg:hidden">
                            <NextStep a={a} />
                          </div>
                        </td>
                        <td className="tabular px-4 py-4 text-base font-semibold text-fg">{inr(a.requested_amount)}</td>
                        <td className="px-4 py-4">
                          <ScoreCell a={a} />
                        </td>
                        <td className="hidden px-4 py-4 lg:table-cell">
                          <NextStep a={a} />
                        </td>
                        <td className="pr-6">
                          <ChevronRight className="h-5 w-5 text-fg-subtle transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </Card>

          {apps.data && (
            <ChangedHint
              action={
                unseen.length > 0 ? (
                  <Button size="sm" variant="ghost" loading={seen.isPending} onClick={() => seen.mutate({ entity_type: "application", all: true })}>
                    Mark all seen ({unseen.length})
                  </Button>
                ) : undefined
              }
            />
          )}
        </TabsContent>
      </Tabs>

      <Sheet open={filtering} onOpenChange={setFiltering} title="Filter applications" description="Narrow the list. The tab counts change with your filters.">
        <div className="space-y-4">
          <Field label="Factory, ID or application number">
            <Input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="e.g. Sharma or UP-F0001" />
          </Field>
          <Field label="Band">
            <Select value={filters.band} onChange={(e) => setFilters({ ...filters, band: e.target.value as Filters["band"] })}>
              <option value="">Any band</option>
              {(Object.keys(BAND_LABEL) as Band[]).map((b) => (
                <option key={b} value={b}>
                  {BAND_LABEL[b]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Cluster">
            <Select value={filters.cluster} onChange={(e) => setFilters({ ...filters, cluster: e.target.value })}>
              <option value="">Any cluster</option>
              {clusters.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex gap-2 pt-2">
            <Button variant="primary" onClick={() => setFiltering(false)}>
              Show {filtered.length} application{filtered.length === 1 ? "" : "s"}
            </Button>
            <Button variant="ghost" onClick={() => setFilters({ q: "", band: "", cluster: "" })}>
              Clear
            </Button>
          </div>
        </div>
      </Sheet>

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
