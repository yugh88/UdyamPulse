import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CircleCheck, Database, HardDrive, Layers, Server, TriangleAlert, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, CHART, ChartFrame, GRID, TOOLTIP, X_AXIS } from "../components/charts";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { num } from "../lib/format";
import { dateTime } from "../lib/time";

interface Check {
  ok: boolean;
  ms: number;
  error?: string;
  dialect?: string;
  backend?: string;
}
interface Ready {
  status: "ready" | "not_ready";
  version: string;
  checks: Record<"database" | "model" | "lake" | "cache", Check>;
}
interface BatchRun {
  id: string;
  kind: string;
  month: number;
  status: string;
  shards: number;
  accounts: number | null;
  chunks: number | null;
  started_at: string | null;
  finished_at: string | null;
}

/** `/readyz` lives outside the versioned API and answers 503 when a dependency is down; both carry the checks. */
async function readyz(): Promise<Ready & { roundtrip_ms: number }> {
  const t0 = performance.now();
  const res = await fetch("/api/readyz", { credentials: "same-origin" });
  const body = (await res.json()) as Ready;
  return { ...body, roundtrip_ms: Math.round(performance.now() - t0) };
}

const CHECKS: { key: keyof Ready["checks"]; label: string; icon: LucideIcon; detail: (c: Check) => string }[] = [
  { key: "database", label: "Database", icon: Database, detail: (c) => c.dialect ?? "" },
  { key: "cache", label: "Cache and queue", icon: Layers, detail: (c) => (c.backend === "memory" ? "built in (demo)" : (c.backend ?? "")) },
  { key: "model", label: "Scoring model", icon: Server, detail: () => "model file loaded" },
  { key: "lake", label: "Data lake", icon: HardDrive, detail: () => "final data layer present" },
];

const PATH = ["Browser", "Web (React)", "API (FastAPI)", "Agents and scoring engine", "Database and data lake", "Worker (jobs, batch)"];

const rate = (r: BatchRun) => {
  if (!r.accounts || !r.started_at || !r.finished_at) return null;
  const s = (new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000;
  return s > 0 ? r.accounts / s : null;
};

export default function System() {
  const ready = useQuery({ queryKey: ["readyz"], queryFn: readyz, refetchInterval: 10_000 });
  const runs = useQuery({ queryKey: ["batch-runs"], queryFn: () => api<BatchRun[]>("/system/batch-runs?limit=10") });
  const [samples, setSamples] = useState<{ t: string; api: number; db: number }[]>([]);
  useEffect(() => {
    if (!ready.data) return;
    const d = ready.data;
    setSamples((s) => [...s.slice(-29), { t: new Date().toLocaleTimeString("en-IN", { hour12: false }), api: d.roundtrip_ms, db: d.checks.database.ms }]);
  }, [ready.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const healthy = ready.data?.status === "ready";
  const done = (runs.data ?? []).filter((r) => r.status === "succeeded" || r.status === "done" || r.finished_at);

  return (
    <div className="space-y-6">
      <PageHeader
        title="System"
        description="Is the platform healthy right now, and how fast is it? Every number here is measured, never estimated."
        aside={
          ready.data && (
            <Badge
              tone={healthy ? "success" : "danger"}
              icon={healthy ? <CircleCheck className="h-3.5 w-3.5" aria-hidden /> : <TriangleAlert className="h-3.5 w-3.5" aria-hidden />}
            >
              {healthy ? "Healthy" : "Degraded"}
            </Badge>
          )
        }
      />

      {ready.isError ? (
        <Card>
          <ErrorState title="Health check failed" error={ready.error} onRetry={() => ready.refetch()} />
        </Card>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {CHECKS.map(({ key, label, icon: Icon, detail }) => {
            const c = ready.data?.checks[key];
            return (
              <div key={key} className="rounded-card border border-edge bg-panel px-6 py-5 shadow-card">
                <div className="flex items-center justify-between gap-2">
                  <p className="label-caps inline-flex items-center gap-2">
                    <Icon className="h-4 w-4" aria-hidden />
                    {label}
                  </p>
                  {c && (
                    <Badge tone={c.ok ? "success" : "danger"} icon={c.ok ? <CircleCheck className="h-3 w-3" aria-hidden /> : <TriangleAlert className="h-3 w-3" aria-hidden />}>
                      {c.ok ? "Healthy" : "Down"}
                    </Badge>
                  )}
                </div>
                {c ? (
                  <>
                    <p className="tabular mt-2 text-[28px] font-bold tracking-[-0.5px] text-fg">{c.ms} ms</p>
                    <p className="text-13 text-fg-muted">{c.ok ? detail(c) : `error: ${c.error}`}</p>
                  </>
                ) : (
                  <Skeleton className="mt-3 h-9 w-24" />
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card
          title="Response time, live"
          description="Measured from this browser every 10 seconds while the page is open: the full health-check request, and the database check inside it."
        >
          {samples.length < 2 ? (
            <Skeleton className="h-60" />
          ) : (
            <>
              <ChartFrame height={240} label={`Readiness round trip, latest ${samples[samples.length - 1].api} ms; database check ${samples[samples.length - 1].db} ms.`}>
                <ResponsiveContainer>
                  <LineChart data={samples} margin={{ top: 10, right: 14, left: -10, bottom: 0 }}>
                    <CartesianGrid {...GRID} />
                    <XAxis dataKey="t" {...X_AXIS} interval="preserveStartEnd" minTickGap={40} />
                    <YAxis {...AXIS} width={44} unit=" ms" />
                    <Tooltip {...TOOLTIP} formatter={(v: number, n: string) => [`${v} ms`, n === "api" ? "Round trip" : "Database check"]} />
                    <Line dataKey="api" stroke={CHART[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line dataKey="db" stroke={CHART[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartFrame>
              <ul className="mt-2 flex gap-5 text-13 text-fg-muted">
                <li className="inline-flex items-center gap-2">
                  <span className="h-[3px] w-4 rounded-full" style={{ background: CHART[0] }} aria-hidden />
                  Round trip
                </li>
                <li className="inline-flex items-center gap-2">
                  <span className="h-[3px] w-4 rounded-full" style={{ background: CHART[1] }} aria-hidden />
                  Database check
                </li>
              </ul>
            </>
          )}
        </Card>
        <Card title="Request path" description={ready.data ? `Version ${ready.data.version}` : undefined}>
          <ol className="space-y-2">
            {PATH.map((p, i) => (
              <li key={p} className="flex items-center gap-3 text-sm text-fg">
                <span className="tabular flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-panel-2 text-xs font-semibold text-fg-muted">{i + 1}</span>
                {p}
                {i < PATH.length - 1 && <ArrowRight className="ml-auto h-4 w-4 text-fg-subtle" aria-hidden />}
              </li>
            ))}
          </ol>
        </Card>
      </div>

      <Card title="Benchmarks" description="These batch runs were measured on this server. The load test has not been run yet, so there is no number.">
        {runs.isLoading ? (
          <Skeleton className="h-40" />
        ) : runs.isError ? (
          <ErrorState error={runs.error} onRetry={() => runs.refetch()} />
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                {["Benchmark", "Result", "When", "Kind"].map((h) => (
                  <th key={h} scope="col" className="label-caps pb-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-edge">
              {done.slice(0, 5).map((r) => {
                const v = rate(r);
                return (
                  <tr key={r.id}>
                    <td className="py-2.5 text-fg">
                      Early-warning batch · {num(r.accounts)} accounts · {r.shards} shard{r.shards === 1 ? "" : "s"}
                    </td>
                    <td className="tabular py-2.5 font-semibold text-fg">{v ? `${num(v)} accounts/s` : r.status}</td>
                    <td className="tabular py-2.5 text-fg-muted">{dateTime(r.finished_at)}</td>
                    <td className="py-2.5">
                      <Badge tone="success">Measured</Badge>
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td className="py-2.5 text-fg">Load test: 50 to 300 simulated users (k6)</td>
                <td className="py-2.5 text-fg-muted">Not run yet</td>
                <td className="py-2.5 text-fg-muted">–</td>
                <td className="py-2.5">
                  <Badge>Pending</Badge>
                </td>
              </tr>
            </tbody>
          </table>
        )}
        {!runs.isLoading && !runs.isError && done.length === 0 && (
          <EmptyState className="py-6" title="No batch run yet" description="The risk head can start the nightly early-warning run. Its speed will show here." />
        )}
      </Card>
    </div>
  );
}
