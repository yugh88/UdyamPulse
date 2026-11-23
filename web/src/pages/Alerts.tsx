import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CheckCheck, FastForward, Lightbulb, Play } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { BeforeAfter, ChangeBadge, ChangedBar, ChangedHint } from "../components/change";
import { AXIS, CHART, ChartFrame, GRID, TOOLTIP, X_AXIS } from "../components/charts";
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  Select,
  SeverityPill,
  Skeleton,
  SkeletonRows,
  TabCount,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  Tooltip as Tip,
  useUrlTab,
} from "../components/ui";
import { api, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useMarkSeen } from "../lib/changes";
import { cn } from "../lib/cn";
import { runJob } from "../lib/jobs";
import { nextStepSentence } from "../lib/alerts";
import { monthLabel } from "../lib/time";
import type { AdvanceResult, AlertDetail, AlertRow, AppDetail, SignalPoint } from "../lib/types";

const TABS = ["open", "acted", "resolved"] as const;
type TabKey = (typeof TABS)[number];
const TAB_LABEL: Record<TabKey, string> = { open: "Open", acted: "Acted on", resolved: "Resolved" };
const tabOf = (a: AlertRow): TabKey => (a.status === "OPEN" ? "open" : a.outcome === "resolved" ? "resolved" : "acted");

/** What each early-warning rule means, in plain words. */
export const RULE_PLAIN: Record<string, string> = {
  order_loss: "Orders falling fast",
  cash_squeeze: "Cash is running short",
  buyer_risk: "Depends on one buyer",
  diversion: "Sales ≠ bank deposits",
  compliance_slip: "GST filed late",
  anomaly: "Unusual pattern",
};
const plain = (a: { rules: string[]; reasons: string[] }) => RULE_PLAIN[a.rules[0]] ?? a.reasons[0] ?? "Warning signs found";
const age = (d: number) => (d <= 0 ? "Today" : d === 1 ? "1 day" : `${d} days`);
/** "2026-07" → "Jul 2026"; other period labels ("8-week baseline") as they are. */
const period = (p: string) => (/^\d{4}-\d{2}(-\d{2})?$/.test(p) ? monthLabel(p) : p);

const ACTIONS = ["visit", "call", "limit review", "visit + limit review", "restructure", "no action"] as const;
const OUTCOMES = ["monitoring", "resolved", "escalated", "no contact"] as const;
const STORY_WEEKS = 6;

/** 24 months of the triggering signals, indexed to their first-year average (= 100) so they share one axis. */
function AlertChart({ signals, keys, labels, alertMonth }: { signals: SignalPoint[]; keys: (keyof SignalPoint)[]; labels: string[]; alertMonth: string }) {
  const rows = useMemo(() => {
    const last = signals.slice(-24);
    // A zero reading means no data that month (before the factory started filing or metering), not a collapse to
    // zero, so it is a gap in the line. The base is the average of the first 12 months that have data.
    const val = (p: SignalPoint, k: keyof SignalPoint) => {
      const v = p[k] as number | null;
      return v == null || !Number.isFinite(v) || v <= 0 ? null : v;
    };
    const base = Object.fromEntries(
      keys.map((k) => {
        const first = last
          .map((p) => val(p, k))
          .filter((v): v is number => v != null)
          .slice(0, 12);
        const mean = first.reduce((a, b) => a + b, 0) / Math.max(1, first.length);
        return [k, mean || 1];
      }),
    );
    return last.map((p) => ({
      month: p.month,
      ...Object.fromEntries(
        keys.map((k) => {
          const v = val(p, k);
          return [k, v == null ? null : Math.round((v / base[k]) * 1000) / 10];
        }),
      ),
    }));
  }, [signals, keys]);
  if (rows.length < 3) return <EmptyState title="No signal history" description="History shows only while the owner's consent is on." className="py-8" />;
  const idx = rows.findIndex((r) => r.month === alertMonth);
  const from = rows[Math.max(0, (idx >= 0 ? idx : rows.length - 1) - 1)].month;
  const to = rows[rows.length - 1].month;
  const lastRow = rows[rows.length - 1] as Record<string, number | string | null>;
  const peak = Math.max(140, ...rows.flatMap((r) => keys.map((k) => (r as unknown as Record<string, number | null>)[k] ?? 0)));
  const top = Math.ceil(peak / 35) * 35;
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-[650] text-fg">Last {rows.length} months</h3>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-13 text-fg-muted">
          {keys.map((k, i) => (
            <li key={k} className="inline-flex items-center gap-2">
              <span className="h-[3px] w-4 rounded-full" style={{ background: CHART[i] }} aria-hidden />
              {labels[i]}
            </li>
          ))}
          <li>index, first year = 100</li>
        </ul>
      </div>
      <ChartFrame
        height={280}
        label={`${labels.join(" and ")} indexed to their first-year average, ${monthLabel(rows[0].month)} to ${monthLabel(to)}. Latest: ${keys.map((k, i) => `${labels[i]} ${lastRow[k] ?? "no data"}`).join(", ")}.`}
      >
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 26, right: 14, left: -10, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <ReferenceArea
              x1={from}
              x2={to}
              fill="var(--brand-tint)"
              fillOpacity={1}
              strokeOpacity={0}
              label={{ value: `Since ${monthLabel(from).split(" ")[0]}`, position: "top", offset: 8, fontSize: 12, fontWeight: 600, fill: "var(--brand)" }}
            />
            <ReferenceLine y={100} stroke="var(--text-subtle)" strokeDasharray="5 4" />
            <XAxis dataKey="month" {...X_AXIS} interval={2} tickFormatter={(m: string) => monthLabel(m).split(" ")[0]} />
            <YAxis {...AXIS} width={44} domain={[0, top]} ticks={Array.from({ length: top / 35 + 1 }, (_, i) => i * 35)} allowDataOverflow={false} />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: string) => monthLabel(m)}
              formatter={(v: unknown, n: string) => [typeof v === "number" ? v.toFixed(0) : "no data", labels[keys.indexOf(n as keyof SignalPoint)] ?? n]}
            />
            {keys.map((k, i) => (
              <Line key={k} dataKey={k} stroke={CHART[i]} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
            ))}
            {keys.map((k, i) =>
              lastRow[k] == null ? null : <ReferenceDot key={`end-${k}`} x={to} y={lastRow[k] as number} r={5} fill="var(--surface)" stroke={CHART[i]} strokeWidth={2.5} isFront />,
            )}
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
    </div>
  );
}

function LogAction({ alert, open, onOpenChange, onDone }: { alert: AlertDetail; open: boolean; onOpenChange: (o: boolean) => void; onDone: () => void }) {
  const suggested = ACTIONS.find((a) => a === alert.next_best_action) ?? "visit";
  const [action, setAction] = useState<string>(suggested);
  const [outcome, setOutcome] = useState<string>("monitoring");
  const [note, setNote] = useState("");
  const log = useMutation({
    mutationFn: () => post(`/alerts/${alert.id}/action`, { action, note, outcome }),
    onSuccess: () => {
      toast.success(`Action logged for ${alert.name}: ${action}`);
      onOpenChange(false);
      onDone();
    },
    onError: (e) => toast.error(`Could not log the action: ${(e as Error).message}`),
  });
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Log action"
      description={`${alert.name} · moves the alert to “Acted on” and adds it to the timeline`}
      footer={
        <>
          <Button onClick={() => onOpenChange(false)} disabled={log.isPending}>
            Cancel
          </Button>
          <Button variant="primary" loading={log.isPending} onClick={() => log.mutate()} icon={<Check className="h-4 w-4" aria-hidden />}>
            Save action
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Action taken">
            <Select value={action} onChange={(e) => setAction(e.target.value)}>
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Outcome">
            <Select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              {OUTCOMES.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Note" hint="What you saw and what you agreed with the owner.">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
        </Field>
      </div>
    </Dialog>
  );
}

function AlertDetailPane({ id, canAct, onChanged }: { id: number; canAct: boolean; onChanged: () => void }) {
  const [logging, setLogging] = useState(false);
  const d = useQuery({ queryKey: ["alert", id], queryFn: () => api<AlertDetail>(`/alerts/${id}`) });
  const app = useQuery({ queryKey: ["application", d.data?.application_id], queryFn: () => api<AppDetail>(`/applications/${d.data!.application_id}`), enabled: !!d.data });
  const ack = useMutation({
    mutationFn: () => post<{ updated: number }>("/alerts/bulk", { ids: [id], action: "acknowledge" }),
    onSuccess: () => (toast.success("Alert acknowledged. It stays open until you log an action."), onChanged()),
    onError: (e) => toast.error(`Could not acknowledge: ${(e as Error).message}`),
  });

  if (d.isLoading)
    return (
      <Card>
        <div role="status" aria-label="Loading alert" className="space-y-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
          <div className="grid grid-cols-3 gap-4">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
          <Skeleton className="h-72" />
        </div>
      </Card>
    );
  if (d.isError || !d.data)
    return (
      <Card>
        <ErrorState error={d.error} onRetry={() => d.refetch()} />
      </Card>
    );
  const a = d.data;
  const tiles = a.signals.slice(0, 2);
  const chartKeys = tiles.map((s) => s.key).filter((k) => app.data?.signals[0] && k in app.data.signals[0]) as (keyof SignalPoint)[];

  return (
    <Card className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-xl font-bold tracking-[-0.3px] text-fg">{a.name}</h2>
            <SeverityPill severity={a.severity} />
          </div>
          <p className="mt-1.5 text-[15px] text-fg-muted">
            {plain(a)}
            {a.reasons[0] ? ` · ${a.reasons[0]}` : ""}
          </p>
        </div>
        <p className="tabular text-13 text-fg-muted">Raised {monthLabel(a.raised_on)}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        {tiles.map((s) => (
          <div key={s.key} className="rounded-control bg-panel-2 px-5 py-4">
            <p className="label-caps">{s.label}</p>
            <BeforeAfter before={s.before} after={s.after} unit={s.unit} goodWhenUp={s.good_when_up} size="lg" className="mt-2" />
            <p className="mt-1 text-xs text-fg-muted">
              {period(s.before_period)} → {period(s.after_period)}
            </p>
          </div>
        ))}
        {a.score && (
          <div className="rounded-control bg-panel-2 px-5 py-4">
            <p className="label-caps">Health score</p>
            <BeforeAfter before={a.score.before} after={a.score.after} goodWhenUp size="lg" className="mt-2" />
            {a.score.before_period && (
              <p className="mt-1 text-xs text-fg-muted">
                {period(a.score.before_period)} → {period(a.score.after_period ?? "")}
              </p>
            )}
          </div>
        )}
      </div>

      {app.isLoading ? (
        <Skeleton className="h-72" />
      ) : app.data && chartKeys.length ? (
        <AlertChart
          signals={app.data.signals}
          keys={chartKeys}
          labels={tiles.filter((s) => chartKeys.includes(s.key as keyof SignalPoint)).map((s) => s.label)}
          alertMonth={a.month}
        />
      ) : (
        <EmptyState title="No signal history" description="History shows only while the owner's consent is on." className="py-8" />
      )}

      {a.status === "OPEN" ? (
        <div className="flex flex-wrap items-center gap-4 rounded-card bg-purple-tint px-5 py-4">
          <Lightbulb className="h-6 w-6 shrink-0 text-purple" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-base font-semibold text-purple">Suggested next step</p>
            <p className="text-[15px] text-fg">{nextStepSentence(a.next_best_action)}</p>
          </div>
          <Tip content={canAct ? "Shows you have seen this alert. It stays open until you log an action." : "Only relationship managers and credit officers can act on alerts."}>
            <span tabIndex={canAct ? -1 : 0}>
              <Button size="lg" disabled={!canAct} loading={ack.isPending} onClick={() => ack.mutate()} icon={<CheckCheck className="h-4 w-4" aria-hidden />}>
                Acknowledge
              </Button>
            </span>
          </Tip>
          <Tip content={canAct ? null : "Only relationship managers and credit officers can act on alerts."}>
            <span tabIndex={canAct ? -1 : 0}>
              <Button variant="primary" size="lg" disabled={!canAct} onClick={() => setLogging(true)} icon={<Check className="h-4 w-4" aria-hidden />}>
                {a.next_best_action.startsWith("visit") ? "Log visit" : "Log action"}
              </Button>
            </span>
          </Tip>
        </div>
      ) : (
        <p className="rounded-card bg-success-tint px-5 py-4 text-sm text-fg">
          <span className="font-semibold text-success">Acted on: </span>
          {a.action_taken}
          {a.outcome ? ` · outcome: ${a.outcome}` : ""}
        </p>
      )}

      <Link to={`/console/${a.application_id}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-info hover:underline">
        Open the account <ArrowRight className="h-4 w-4" aria-hidden />
      </Link>
      {logging && <LogAction alert={a} open={logging} onOpenChange={setLogging} onDone={onChanged} />}
    </Card>
  );
}

export default function Alerts() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const canAct = session!.role === "rm" || session!.role === "credit_officer";
  const [tab] = useUrlTab(TABS, "open");
  const [params, setParams] = useSearchParams();
  const seen = useMarkSeen();
  const [story, setStory] = useState<{ week: number; newAlerts: number } | null>(null);
  const storyStop = useRef(false);

  const alerts = useQuery({ queryKey: ["alerts", "ALL"], queryFn: () => api<AlertRow[]>("/alerts?status=ALL") });
  const refresh = () =>
    Promise.all(["alerts", "alert", "portfolio", "migration", "clock", "nav-counts", "application", "changes"].map((k) => qc.invalidateQueries({ queryKey: [k] })));

  const advance = useMutation({
    mutationFn: () => runJob<AdvanceResult>("/sim/advance?days=7"),
    onSuccess: async (r) => {
      window.dispatchEvent(new Event("sim-advanced"));
      await refresh();
      const blocked = r.blocked.length ? ` ${r.blocked.length} account(s) skipped: consent revoked.` : "";
      toast.success(`One week later (${monthLabel(r.sim_date)}): ${r.new_alerts.length} new alert${r.new_alerts.length === 1 ? "" : "s"}.${blocked}`);
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
        window.dispatchEvent(new Event("sim-advanced"));
        await refresh();
      }
      toast.success(`Six weeks later: ${total} new alert${total === 1 ? "" : "s"} raised by the early-warning agent.`);
    } catch (e) {
      toast.error(`The demo stopped: ${(e as Error).message}`);
    } finally {
      setStory(null);
    }
  }

  const counts = useMemo(() => {
    const c: Record<TabKey, number> = { open: 0, acted: 0, resolved: 0 };
    (alerts.data ?? []).forEach((a) => c[tabOf(a)]++);
    return c;
  }, [alerts.data]);
  const rows = useMemo(() => (alerts.data ?? []).filter((a) => tabOf(a) === tab), [alerts.data, tab]);
  const selectedId = Number(params.get("alert")) || rows[0]?.id || null;
  const select = (id: number) => {
    setParams(
      (p) => {
        const n = new URLSearchParams(p);
        n.set("alert", String(id));
        return n;
      },
      { replace: true },
    );
    const row = alerts.data?.find((a) => a.id === id);
    if (row?.changed_since_seen) seen.mutate({ entity_type: "alert", ids: [id] });
  };
  const busy = advance.isPending || story !== null;
  // "Mark all seen" counts what this list shows, so the number always matches the pink bars on screen.
  const unseen = rows.filter((a) => a.changed_since_seen).length;
  const unseenIn = (k: TabKey) => (alerts.data ?? []).some((a) => tabOf(a) === k && a.changed_since_seen);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Early-warning alerts"
        description="Factories whose signals turned bad. Act before a payment is missed."
        actions={
          <>
            <Button size="lg" variant="ghost" disabled={busy} onClick={playStory} icon={<Play className="h-4 w-4" aria-hidden />}>
              Play 6 weeks
            </Button>
            <Button size="lg" disabled={busy} loading={advance.isPending} onClick={() => advance.mutate()} icon={<FastForward className="h-4 w-4" aria-hidden />}>
              Fast-forward 1 week
            </Button>
          </>
        }
      />

      {story && (
        <div role="status" className="rounded-card border border-edge bg-purple-tint px-5 py-3">
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
            <div className="h-full rounded-full bg-purple transition-[width] duration-200" style={{ width: `${(story.week / STORY_WEEKS) * 100}%` }} />
          </div>
        </div>
      )}

      <Tabs
        value={tab}
        onValueChange={(t) =>
          setParams(
            (p) => {
              const n = new URLSearchParams(p);
              n.delete("alert");
              if (t === "open") n.delete("tab");
              else n.set("tab", t);
              return n;
            },
            { replace: true },
          )
        }
      >
        <TabsList aria-label="Alert status">
          {TABS.map((k) => (
            <TabsTrigger key={k} value={k}>
              {TAB_LABEL[k]}
              <TabCount value={alerts.data ? counts[k] : null} />
              {k !== tab && unseenIn(k) && (
                <span className="h-2 w-2 rounded-full bg-brand" title="Has alerts that changed since you last looked">
                  <span className="sr-only">, has changes since you last looked</span>
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={tab}>
          {alerts.isError ? (
            <Card>
              <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} />
            </Card>
          ) : (
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(300px,0.8fr)_minmax(0,2fr)]">
              <div className="space-y-3">
                <Card padded={false} className="overflow-hidden">
                  {alerts.isLoading ? (
                    <div className="p-5">
                      <SkeletonRows rows={5} />
                    </div>
                  ) : rows.length === 0 ? (
                    <EmptyState
                      title={tab === "open" ? "No open alerts" : tab === "acted" ? "Nothing acted on yet" : "Nothing resolved yet"}
                      description={tab === "open" ? "Fast-forward the clock so the early-warning agent can check new data." : "Alerts move here when an action is logged."}
                    />
                  ) : (
                    <ul aria-label={`${TAB_LABEL[tab]} alerts`} className="divide-y divide-edge">
                      {rows.map((a) => {
                        const on = a.id === selectedId;
                        return (
                          <li key={a.id} className="relative">
                            <ChangedBar show={a.changed_since_seen} />
                            <button
                              type="button"
                              aria-current={on ? "true" : undefined}
                              aria-label={`Open ${a.severity} alert for ${a.name}`}
                              onClick={() => select(a.id)}
                              className={cn(
                                "flex w-full items-start gap-3 py-4 pr-5 pl-6 text-left transition-colors duration-150",
                                on ? "bg-primary-tint" : "hover:bg-panel-2/60",
                              )}
                            >
                              <span className="min-w-0 flex-1">
                                <span className="flex flex-wrap items-center gap-2">
                                  <span className="text-[15px] font-semibold text-fg">{a.name}</span>
                                  <ChangeBadge kind={a.changed_since_seen ? a.change_kind : null} />
                                </span>
                                <span className="mt-0.5 block text-sm text-fg-muted">{plain(a)}</span>
                              </span>
                              <span className="flex shrink-0 flex-col items-end gap-1.5">
                                <SeverityPill severity={a.severity} />
                                <span className="text-13 text-fg-muted">{age(a.days_open)}</span>
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Card>
                {alerts.data && (
                  <ChangedHint
                    action={
                      unseen > 0 ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          loading={seen.isPending}
                          onClick={() => seen.mutate({ entity_type: "alert", ids: rows.filter((a) => a.changed_since_seen).map((a) => a.id) })}
                        >
                          Mark all seen ({unseen})
                        </Button>
                      ) : undefined
                    }
                  />
                )}
              </div>
              {selectedId && rows.some((r) => r.id === selectedId) ? (
                <AlertDetailPane key={selectedId} id={selectedId} canAct={canAct} onChanged={refresh} />
              ) : alerts.isLoading ? (
                <Skeleton className="h-[520px]" />
              ) : rows.length ? (
                <Card>
                  <EmptyState title="Select an alert" description="Pick an alert on the left to see what changed and what to do." />
                </Card>
              ) : null}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
