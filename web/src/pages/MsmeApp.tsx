import "@fontsource-variable/noto-sans-devanagari";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUp,
  ArrowDown,
  CircleCheck,
  CircleDot,
  Download,
  Home,
  ListChecks,
  MessageCircle,
  ShieldCheck,
  ShieldOff,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { AXIS, ChartFrame, GRID, TOOLTIP, X_AXIS } from "../components/charts";
import { Badge, Button, Card, Dialog, EmptyState, ErrorState, Field, Skeleton, Textarea } from "../components/ui";
import { setLang, type Lang } from "../i18n";
import { api, del, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn } from "../lib/cn";
import { inr, type Band } from "../lib/format";
import { dateTime, monthLabel } from "../lib/time";
import type { AppDetail, Consent, Pillar, Reason } from "../lib/types";

interface PlanStep {
  key: string;
  phase: string;
  phase_hi: string;
  pillar: string;
  action: string;
  action_hi: string;
  done: boolean;
}
interface Forecast {
  method: string;
  history: { month: string; actual: number }[];
  forecast: { month: string; yhat: number; lo: number; hi: number }[];
  negative_months: string[];
}
interface Readiness {
  factory_id: string;
  name: string;
  application_id: number;
  state: string;
  decision: "APPROVED" | "REJECTED" | null;
  review_requested: boolean;
  consent: Consent;
  data_stale: boolean;
  data_month?: string;
  score: number | null;
  band: Band | null;
  pillars?: (Pillar & { label_hi: string })[];
  reasons?: (Reason & { text_hi: string })[];
  plan: { target: number; points_to_target: number; summary: string; hindi_summary: string; steps: PlanStep[]; steps_done: number; forecast: Forecast } | null;
}
interface Note {
  id: number;
  channel: string;
  text: string;
  text_hi: string | null;
  sim_date: string;
}
interface MyData {
  purpose: string;
  data_categories: string[];
  not_collected: string[];
  snapshots_held: number;
  retention: string;
  consent_ledger: { ts: string; event: string; actor: string }[];
}

type TabKey = "home" | "plan" | "consent";
const TABS: { key: TabKey; icon: LucideIcon }[] = [
  { key: "home", icon: Home },
  { key: "plan", icon: ListChecks },
  { key: "consent", icon: ShieldCheck },
];

/** Loan-readiness ring: the score's place on the 300–900 scale, with the score in the middle. */
function ReadinessRing({ score, band, label }: { score: number | null; band: Band | null; label: string }) {
  const { t } = useTranslation();
  const r = 62;
  const c = 2 * Math.PI * r;
  const f = score == null ? 0 : Math.min(1, Math.max(0, (score - 300) / 600));
  const colour = band === "HIGH_RISK" ? "var(--danger)" : band === "WATCH" ? "var(--warning)" : "var(--primary)";
  return (
    <figure role="img" aria-label={score == null ? label : `${label}: ${score} ${t("home.outOf")}`} className="relative h-40 w-40">
      <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90">
        <circle cx={80} cy={80} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={14} />
        <circle
          cx={80}
          cy={80}
          r={r}
          fill="none"
          stroke={colour}
          strokeWidth={14}
          strokeLinecap="round"
          strokeDasharray={`${c * f} ${c}`}
          style={{ transition: "stroke-dasharray 600ms ease-out" }}
        />
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tabular text-[40px] leading-none font-bold tracking-[-1px] text-fg">{score ?? "–"}</span>
        <span className="mt-1 text-xs text-fg-muted">{t("home.outOf")}</span>
      </span>
    </figure>
  );
}

function ForecastChart({ forecast }: { forecast: Forecast }) {
  const { t } = useTranslation();
  const hist = forecast.history.slice(-9).map((h) => ({ month: h.month, actual: h.actual / 1e5 }));
  const last = hist[hist.length - 1];
  const fc = forecast.forecast.map((f) => ({ month: f.month, forecast: f.yhat / 1e5, range: [f.lo / 1e5, f.hi / 1e5] as [number, number] }));
  const rows = [...hist.slice(0, -1), { ...last, forecast: last.actual, range: [last.actual, last.actual] as [number, number] }, ...fc];
  const names: Record<string, string> = { actual: t("home.forecastLegendActual"), forecast: t("home.forecastLegendForecast"), range: t("home.forecastLegendRange") };
  return (
    <>
      <ChartFrame height={190} label={`${t("home.forecast")}: ${fc.map((f) => `${monthLabel(f.month)} ${t("home.lakh", { value: f.forecast.toFixed(1) })}`).join(", ")}`}>
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="month" {...X_AXIS} interval={2} tickFormatter={(m: string) => monthLabel(m).slice(0, 3)} />
            <YAxis {...AXIS} tickFormatter={(v: number) => `${Math.round(v)}L`} width={44} />
            <ReferenceLine y={0} stroke="var(--border-strong)" />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: string) => monthLabel(m)}
              formatter={(v: number | [number, number], name: string) => [
                Array.isArray(v) ? `${v[0].toFixed(1)} – ${v[1].toFixed(1)}` : t("home.lakh", { value: v.toFixed(1) }),
                names[name] ?? name,
              ]}
            />
            <Area dataKey="range" fill="var(--chart-1)" fillOpacity={0.14} stroke="none" isAnimationActive={false} />
            <Line dataKey="actual" stroke="var(--chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="forecast" stroke="var(--chart-1)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>
      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
        <li className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-chart-1" aria-hidden />
          {names.actual}
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span className="h-0 w-4 border-t-2 border-dashed border-chart-1" aria-hidden />
          {names.forecast}
        </li>
        <li className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm bg-chart-1/20" aria-hidden />
          {names.range}
        </li>
      </ul>
    </>
  );
}

export default function MsmeApp() {
  const { session } = useAuth();
  const fid = session!.factory_id!;
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "hi" ? "hi" : "en") as Lang;
  const hi = lang === "hi";
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabKey>("home");
  const [revoking, setRevoking] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [note, setNote] = useState("");

  const r = useQuery({ queryKey: ["msme", fid, "readiness"], queryFn: () => api<Readiness>(`/msme/${fid}/readiness`) });
  // The owner's own application: the recommended limit and last month's score, for "you can ask for" and the delta.
  const app = useQuery({
    queryKey: ["msme", fid, "application", r.data?.application_id],
    queryFn: () => api<AppDetail>(`/applications/${r.data!.application_id}`),
    enabled: !!r.data,
    retry: false,
  });
  const notes = useQuery({ queryKey: ["msme", fid, "notifications"], queryFn: () => api<Note[]>(`/msme/${fid}/notifications`), enabled: tab === "home" });
  const mine = useQuery({ queryKey: ["msme", fid, "my-data"], queryFn: () => api<MyData>(`/msme/${fid}/my-data`), enabled: tab === "consent" });
  const refresh = () => qc.invalidateQueries({ queryKey: ["msme", fid] });
  const fail = (e: unknown) => {
    toast.error(`${t("common.error")}: ${(e as Error).message}`);
  };

  const revoke = useMutation({
    mutationFn: () => del(`/applications/${r.data!.application_id}/consent`),
    onSuccess: () => (toast.success(t("consent.revokedToast")), setRevoking(false), refresh()),
    onError: fail,
  });
  const grant = useMutation({
    mutationFn: () => post(`/applications/${r.data!.application_id}/consent`),
    onSuccess: () => (toast.success(t("consent.grantedToast")), refresh()),
    onError: fail,
  });
  const erase = useMutation({ mutationFn: () => post(`/msme/${fid}/erasure-request`), onSuccess: () => toast.success(t("consent.eraseDone")), onError: fail });
  const review = useMutation({
    mutationFn: () => post(`/applications/${r.data!.application_id}/review-request`, { note: note.trim() }),
    onSuccess: () => (toast.success(t("home.reviewDone")), setReviewing(false), setNote(""), refresh()),
    onError: fail,
  });
  const step = useMutation({
    mutationFn: (v: { key: string; done: boolean }) => api(`/msme/${fid}/plan/steps/${v.key}`, { method: "PUT", body: JSON.stringify({ done: v.done }) }),
    // Optimistic: ticking a box should feel instant, and roll back if the save fails.
    onMutate: (v) => {
      void qc.cancelQueries({ queryKey: ["msme", fid, "readiness"] });
      const prev = qc.getQueryData<Readiness>(["msme", fid, "readiness"]);
      if (prev?.plan) {
        const steps = prev.plan.steps.map((s) => (s.key === v.key ? { ...s, done: v.done } : s));
        qc.setQueryData<Readiness>(["msme", fid, "readiness"], { ...prev, plan: { ...prev.plan, steps, steps_done: steps.filter((s) => s.done).length } });
      }
      return { prev };
    },
    onError: (e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["msme", fid, "readiness"], ctx.prev);
      fail(e);
    },
  });

  async function downloadData() {
    try {
      const data = await api<MyData>(`/msme/${fid}/my-data`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `my_data_${fid}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t("consent.downloaded"));
    } catch (e) {
      fail(e);
    }
  }

  const d = r.data;
  const helping = (d?.reasons ?? []).filter((x) => x.points >= 0).slice(0, 2);
  const improve = (d?.reasons ?? []).filter((x) => x.points < 0).sort((a, b) => a.points - b.points)[0];
  const hist = app.data?.score_history ?? [];
  const prev = hist.length >= 2 ? hist[hist.length - 2].score : null;
  const delta = d?.score != null && prev != null ? d.score - prev : null;
  const limit = app.data?.recommended_limit ?? null;
  const consentActive = !!d?.consent.active;
  const consentLabel = consentActive ? t("consent.active") : d?.consent.status === "REVOKED" ? t("consent.revoked") : t("consent.none");
  const readyText = !d?.band ? t("home.notScored") : d.band === "APPROVE" ? t("home.ready") : d.band === "WATCH" ? t("home.almost") : t("home.notReady");
  const statusLine = !d
    ? ""
    : d.state === "MONITORING"
      ? t("home.statusActive")
      : d.decision === "APPROVED"
        ? t("home.statusApproved")
        : d.decision === "REJECTED"
          ? t("home.statusRejected")
          : d.state === "MEMO_DRAFTED"
            ? t("home.statusWithOfficer")
            : t("home.statusAssessing");
  const latest = notes.data?.[notes.data.length - 1];

  return (
    <div lang={lang} className="msme-body mx-auto max-w-xl pb-24 sm:pb-6">
      <header className="mb-5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-13 text-fg-muted">{t("home.greeting", { name: d?.name ?? session!.display_name })}</p>
          <h1 className="text-title font-bold tracking-[-0.5px] text-fg">{t(`titles.${tab}`)}</h1>
        </div>
        <div role="radiogroup" aria-label={t("lang.label")} className="flex shrink-0 items-center rounded-full border border-edge-2 bg-panel p-1">
          {(["en", "hi"] as const).map((l) => (
            <button
              key={l}
              type="button"
              role="radio"
              aria-checked={lang === l}
              aria-label={t(`lang.${l}`)}
              lang={l}
              onClick={() => setLang(l)}
              className={cn(
                "h-9 min-w-11 rounded-full px-3 text-sm font-semibold transition-colors duration-150",
                lang === l ? "bg-primary-tint text-primary" : "text-fg-muted hover:text-fg",
              )}
            >
              {l === "en" ? "EN" : "हिं"}
            </button>
          ))}
        </div>
      </header>

      <nav aria-label="Sections" className="fixed inset-x-0 bottom-0 z-20 border-t border-edge bg-panel sm:static sm:mb-5 sm:rounded-card sm:border sm:p-1">
        <ul role="tablist" className="grid grid-cols-3">
          {TABS.map(({ key, icon: Icon }) => (
            <li key={key} role="presentation">
              <button
                type="button"
                role="tab"
                id={`msme-tab-${key}`}
                aria-selected={tab === key}
                aria-controls="msme-panel"
                onClick={() => setTab(key)}
                className={cn(
                  "flex min-h-14 w-full flex-col items-center justify-center gap-1 px-1 text-13 font-semibold sm:min-h-11 sm:flex-row sm:gap-2 sm:rounded-control",
                  tab === key ? "text-primary sm:bg-primary-tint" : "text-fg-muted hover:text-fg",
                )}
              >
                <Icon className="h-5 w-5" aria-hidden />
                {t(`tabs.${key}`)}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div id="msme-panel" role="tabpanel" aria-labelledby={`msme-tab-${tab}`} className="space-y-4">
        {r.isLoading ? (
          <div role="status" aria-label={t("common.loading")} className="space-y-4">
            <Skeleton className="h-72" />
            <Skeleton className="h-40" />
          </div>
        ) : r.isError || !d ? (
          <ErrorState title={t("common.error")} error={r.error} onRetry={() => r.refetch()} />
        ) : tab === "home" ? (
          <>
            {d.data_stale && (
              <p role="status" className="flex items-start gap-2 rounded-control bg-warning-tint px-4 py-3 text-warning">
                <TriangleAlert className="mt-1 h-4 w-4 shrink-0" aria-hidden />
                {t("home.stale")}
              </p>
            )}
            <Card>
              <div className="flex flex-col items-center text-center">
                <ReadinessRing score={d.score} band={d.band} label={t("home.scoreCaption")} />
                <h2 className="mt-4 text-xl font-bold text-fg">{readyText}</h2>
                {limit != null && d.decision !== "REJECTED" && (
                  <p className="mt-1 text-fg-muted">{t("home.askUpTo", { amount: hi ? inr(limit).replace(" L", " लाख").replace(" Cr", " करोड़") : inr(limit) })}</p>
                )}
                {delta != null && delta !== 0 && (
                  <span
                    className={cn(
                      "mt-3 inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-semibold",
                      delta > 0 ? "bg-success-tint text-success" : "bg-danger-tint text-danger",
                    )}
                  >
                    {delta > 0 ? <ArrowUp className="h-4 w-4" aria-hidden /> : <ArrowDown className="h-4 w-4" aria-hidden />}
                    {t("home.sinceLastMonth", { points: Math.abs(delta) })}
                  </span>
                )}
                {d.data_month && <p className="mt-3 text-xs text-fg-muted">{t("home.dataAsOf", { month: monthLabel(d.data_month) })}</p>}
              </div>
            </Card>

            {d.reasons && (
              <Card>
                <h2 className="text-base font-[650] text-fg">{t("home.helping")}</h2>
                {helping.length ? (
                  <ul className="mt-3 space-y-3">
                    {helping.map((x) => (
                      <li key={x.feature} className="flex items-start gap-3">
                        <CircleCheck className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
                        <span className="text-fg">{hi ? x.text_hi : x.text}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-fg-muted">{t("home.noneHelping")}</p>
                )}
                <h2 className="mt-5 text-base font-[650] text-fg">{t("home.improve")}</h2>
                {improve ? (
                  <p className="mt-3 flex items-start gap-3">
                    <CircleDot className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden />
                    <span className="text-fg">{hi ? improve.text_hi : improve.text}</span>
                  </p>
                ) : (
                  <p className="mt-2 text-fg-muted">{t("home.nothingToImprove")}</p>
                )}
              </Card>
            )}

            <div className="flex items-start gap-3 rounded-card bg-info-tint px-5 py-4">
              <MessageCircle className="mt-0.5 h-5 w-5 shrink-0 text-info" aria-hidden />
              <div className="min-w-0">
                <p className="text-fg">
                  <span className="font-semibold">{t("home.update")}: </span>
                  {latest ? (hi && latest.text_hi ? latest.text_hi : latest.text) : statusLine}
                </p>
                {d.score != null && !d.review_requested && (
                  <button type="button" onClick={() => setReviewing(true)} className="mt-2 min-h-11 text-sm font-semibold text-info hover:underline">
                    {t("home.reviewCta")}
                  </button>
                )}
                {d.review_requested && <p className="mt-1 text-sm text-fg-muted">{t("home.reviewDone")}</p>}
              </div>
            </div>
          </>
        ) : tab === "plan" ? (
          !d.plan ? (
            <Card>
              <EmptyState title={t("plan.title")} description={t("plan.empty")} />
            </Card>
          ) : (
            <>
              <Card>
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-[650] text-fg">{t("plan.title90")}</h2>
                  <Badge tone="success" className="font-semibold">
                    {t("plan.badge", { done: d.plan.steps_done, total: d.plan.steps.length })}
                  </Badge>
                </div>
                <div
                  className="mt-3 h-2.5 overflow-hidden rounded-full bg-panel-2"
                  role="progressbar"
                  aria-label={t("plan.progress", { done: d.plan.steps_done, total: d.plan.steps.length })}
                  aria-valuemin={0}
                  aria-valuemax={d.plan.steps.length}
                  aria-valuenow={d.plan.steps_done}
                >
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-200"
                    style={{ width: `${(d.plan.steps_done / Math.max(1, d.plan.steps.length)) * 100}%` }}
                  />
                </div>
                <p className="sr-only" aria-live="polite">
                  {t("plan.progress", { done: d.plan.steps_done, total: d.plan.steps.length })}
                </p>
                <ul className="mt-2 divide-y divide-edge">
                  {d.plan.steps.map((s) => {
                    const text = hi ? s.action_hi : s.action;
                    return (
                      <li key={s.key}>
                        <label className="flex min-h-14 cursor-pointer items-start gap-3 py-3.5">
                          <input
                            type="checkbox"
                            className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--primary)]"
                            checked={s.done}
                            onChange={(e) => step.mutate({ key: s.key, done: e.target.checked })}
                            aria-label={t("plan.markDone", { step: text })}
                          />
                          <span className="min-w-0 flex-1">
                            <span className={cn("block font-semibold", s.done ? "text-fg-muted line-through" : "text-fg")}>{text}</span>
                            <span className="mt-0.5 block text-13 text-fg-muted">
                              {hi ? s.phase_hi : s.phase} · {t(`plan.pillar.${s.pillar}`)}
                            </span>
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </Card>
              <Card title={t("home.forecast")} description={t("home.forecastSub")}>
                <ForecastChart forecast={d.plan.forecast} />
                <p
                  className={cn(
                    "mt-3 flex items-start gap-2 rounded-control px-3 py-2 text-13",
                    d.plan.forecast.negative_months.length ? "bg-warning-tint text-warning" : "bg-success-tint text-success",
                  )}
                >
                  {d.plan.forecast.negative_months.length ? (
                    <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  ) : (
                    <CircleCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  )}
                  {d.plan.forecast.negative_months.length ? t("home.forecastWarn", { months: d.plan.forecast.negative_months.map(monthLabel).join(", ") }) : t("home.forecastOk")}
                </p>
              </Card>
            </>
          )
        ) : (
          <>
            <Card>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-[650] text-fg">{t("consent.title")}</h2>
                <Badge
                  tone={consentActive ? "success" : "danger"}
                  icon={consentActive ? <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> : <ShieldOff className="h-3.5 w-3.5" aria-hidden />}
                >
                  {consentLabel}
                </Badge>
              </div>
              {mine.isLoading ? (
                <Skeleton className="mt-4 h-40" />
              ) : mine.isError || !mine.data ? (
                <ErrorState title={t("common.error")} error={mine.error} onRetry={() => mine.refetch()} />
              ) : (
                <dl className="mt-4 space-y-4">
                  <div>
                    <dt className="label-caps">{t("consent.what")}</dt>
                    <dd className="mt-1.5 flex flex-wrap gap-1.5">
                      {mine.data.data_categories.map((c) => (
                        <Badge key={c}>{c}</Badge>
                      ))}
                    </dd>
                  </div>
                  <div>
                    <dt className="label-caps">{t("consent.why")}</dt>
                    <dd className="mt-0.5 text-fg">{d.consent.purpose ?? mine.data.purpose}</dd>
                  </div>
                  {consentActive && d.consent.expires_on && (
                    <div>
                      <dt className="label-caps">{t("consent.until")}</dt>
                      <dd className="tabular mt-0.5 text-fg">{monthLabel(d.consent.expires_on)}</dd>
                    </div>
                  )}
                  <div>
                    <dt className="label-caps">{t("consent.notCollected")}</dt>
                    <dd className="mt-0.5 text-fg">{mine.data.not_collected.join(" · ")}</dd>
                  </div>
                </dl>
              )}
              <div className="mt-5 space-y-2">
                {consentActive ? (
                  <Button
                    variant="secondary"
                    size="lg"
                    className="w-full border-danger text-danger hover:bg-danger-tint"
                    onClick={() => setRevoking(true)}
                    icon={<XCircle className="h-5 w-5" aria-hidden />}
                  >
                    {t("consent.revoke")}
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="lg"
                    className="w-full"
                    loading={grant.isPending}
                    onClick={() => grant.mutate()}
                    icon={<ShieldCheck className="h-5 w-5" aria-hidden />}
                  >
                    {t("consent.grant")}
                  </Button>
                )}
                <div className="flex flex-wrap items-center justify-center gap-x-5">
                  <button type="button" onClick={downloadData} className="inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-info hover:underline">
                    <Download className="h-4 w-4" aria-hidden />
                    {t("consent.download")}
                  </button>
                  <button
                    type="button"
                    disabled={erase.isPending}
                    onClick={() => erase.mutate()}
                    className="min-h-11 text-sm font-medium text-fg-muted hover:text-fg hover:underline"
                  >
                    {t("consent.erase")}
                  </button>
                </div>
              </div>
            </Card>
            {mine.data && (
              <Card title={t("consent.history")} description={t("consent.snapshots", { count: mine.data.snapshots_held })}>
                <ol className="space-y-2">
                  {[...mine.data.consent_ledger]
                    .reverse()
                    .slice(0, 8)
                    .map((e, i) => (
                      <li key={`${e.ts}-${i}`} className="flex items-baseline justify-between gap-3 text-13">
                        <span className="text-fg">{t(`consent.events.${e.event}`, { defaultValue: e.event })}</span>
                        <span className="tabular shrink-0 text-xs text-fg-muted">{dateTime(e.ts)}</span>
                      </li>
                    ))}
                </ol>
              </Card>
            )}
          </>
        )}
      </div>

      <Dialog
        open={revoking}
        onOpenChange={setRevoking}
        title={t("consent.revokeTitle")}
        footer={
          <>
            <Button onClick={() => setRevoking(false)} disabled={revoke.isPending}>
              {t("consent.keep")}
            </Button>
            <Button variant="danger" loading={revoke.isPending} onClick={() => revoke.mutate()}>
              {t("consent.revokeConfirm")}
            </Button>
          </>
        }
      >
        <p lang={lang} className="text-sm text-fg">
          {t("consent.revokeBody")}
        </p>
      </Dialog>

      <Dialog
        open={reviewing}
        onOpenChange={setReviewing}
        title={t("home.reviewCta")}
        footer={
          <>
            <Button onClick={() => setReviewing(false)} disabled={review.isPending}>
              {t("home.cancel")}
            </Button>
            <Button variant="primary" loading={review.isPending} disabled={note.trim().length < 3} onClick={() => review.mutate()}>
              {t("home.reviewSend")}
            </Button>
          </>
        }
      >
        <Field label={t("home.reviewLabel")} hint={t("home.reviewHint")}>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
        </Field>
      </Dialog>
    </div>
  );
}
