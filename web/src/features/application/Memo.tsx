import { useQuery } from "@tanstack/react-query";
import { BookOpen, Eye, FileDown, RefreshCw } from "lucide-react";
import { Fragment, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { AiLabel, Button, Card, Dialog, EmptyState, ErrorState, Sheet, Skeleton } from "../../components/ui";
import { api, pdfUrl } from "../../lib/api";
import type { Memo } from "../../lib/types";

const CITE = /\[§(\d+\.\d+)\]/g;

/** Renders text with every [§x.y] turned into a chip that opens the policy clause. */
function Cited({ text, onOpen }: { text: string; onOpen: (section: string) => void }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE)) {
    parts.push(<Fragment key={`t${m.index}`}>{text.slice(last, m.index)}</Fragment>);
    parts.push(
      <button
        key={`c${m.index}`}
        type="button"
        onClick={() => onOpen(m[1])}
        aria-label={`Open policy clause ${m[1]}`}
        className="tabular mx-0.5 inline-flex items-center rounded bg-primary-tint px-1.5 py-px align-baseline text-xs font-medium text-primary hover:underline"
      >
        §{m[1]}
      </button>,
    );
    last = m.index + m[0].length;
  }
  parts.push(<Fragment key="end">{text.slice(last)}</Fragment>);
  return <>{parts}</>;
}

function PolicySheet({ section, onClose }: { section: string | null; onClose: () => void }) {
  const q = useQuery({
    queryKey: ["policy", section],
    queryFn: () => api<{ section: string; title: string; text: string; source: string }>(`/policy/${section}`),
    enabled: !!section,
    staleTime: Infinity,
  });
  return (
    <Sheet
      open={!!section}
      onOpenChange={(o) => !o && onClose()}
      title={q.data ? `§${q.data.section} ${q.data.title}` : `Policy clause §${section ?? ""}`}
      description="Bank credit policy"
    >
      {q.isLoading ? (
        <Skeleton className="h-40" />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.data ? (
        <>
          <p className="text-sm leading-relaxed whitespace-pre-line text-fg">{q.data.text}</p>
          <p className="mt-4 flex items-center gap-1.5 text-xs text-fg-muted">
            <BookOpen className="h-3.5 w-3.5" aria-hidden />
            {q.data.source}
          </p>
        </>
      ) : null}
    </Sheet>
  );
}

const LISTS: { key: "strengths" | "risks" | "mitigants" | "covenants"; title: string }[] = [
  { key: "strengths", title: "Strengths" },
  { key: "risks", title: "Risks" },
  { key: "mitigants", title: "Mitigants" },
  { key: "covenants", title: "Covenants" },
];

const METRIC_LABEL: Record<string, string> = {
  annual_gst_turnover: "Annual GST turnover",
  avg_monthly_eway_value_3m: "Monthly e-way value (3m)",
  eway_trend_3m_vs_12m: "E-way trend, 3m vs 12m",
  kwh_trend_3m_vs_12m: "Power trend, 3m vs 12m",
  bounces_12m: "Bounces in 12 months",
  top_buyer_share: "Top-buyer share",
  days_to_pay: "Days to pay",
  gst_on_time_12m: "GST filed on time",
};

export function MemoView({
  applicationId,
  memo,
  canGenerate,
  generating,
  onGenerate,
  generateHint,
}: {
  applicationId: number;
  memo: Memo | null;
  canGenerate: boolean;
  generating: boolean;
  onGenerate: () => void;
  generateHint?: string;
}) {
  const [section, setSection] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = useState<"preview" | "download" | null>(null);

  async function pdf(mode: "preview" | "download") {
    setPdfBusy(mode);
    try {
      const url = await pdfUrl(`/applications/${applicationId}/memo.pdf`);
      if (mode === "preview") setPreview(url);
      else {
        const a = document.createElement("a");
        a.href = url;
        a.download = `credit_memo_${applicationId}.pdf`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        toast.success("Memo PDF downloaded");
      }
    } catch (e) {
      toast.error(`PDF not available: ${(e as Error).message}`);
    } finally {
      setPdfBusy(null);
    }
  }

  if (!memo) {
    return (
      <Card>
        <EmptyState
          title="No credit memo yet"
          description={generateHint ?? "The memo agent drafts the memo from the score, the data and the bank's policy. Every number comes from the scoring engine."}
          action={
            canGenerate ? (
              <Button variant="primary" loading={generating} onClick={onGenerate}>
                Generate memo
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  }

  return (
    <>
      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-edge bg-primary-tint/50 px-5 py-3">
          <AiLabel />
          <div className="flex items-center gap-2">
            <Button size="sm" loading={pdfBusy === "preview"} onClick={() => pdf("preview")} icon={<Eye className="h-4 w-4" aria-hidden />}>
              Preview PDF
            </Button>
            <Button size="sm" loading={pdfBusy === "download"} onClick={() => pdf("download")} icon={<FileDown className="h-4 w-4" aria-hidden />}>
              Download PDF
            </Button>
            {canGenerate && (
              <Button size="sm" loading={generating} onClick={onGenerate} icon={<RefreshCw className="h-4 w-4" aria-hidden />}>
                Regenerate
              </Button>
            )}
          </div>
        </div>
        <article className="space-y-6 p-5">
          <header>
            <h2 className="text-xl font-semibold text-fg">{memo.title}</h2>
            <p className="mt-1 text-xs text-fg-muted">
              Writer: {memo.llm_provider === "template" ? "deterministic template (local, no external API)" : memo.llm_provider}
              {memo.generated_in_ms != null && <> · generated in {memo.generated_in_ms} ms</>}
            </p>
          </header>

          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-control border border-edge bg-edge sm:grid-cols-4">
            {[
              ["Requested", memo.requested_display],
              ["Recommended limit", memo.recommended_limit_display],
              ["Pricing", memo.pricing_band],
              ["Policy clauses cited", String(memo.citations.length)],
            ].map(([k, v]) => (
              <div key={k} className="bg-panel px-3 py-2.5">
                <dt className="text-xs text-fg-muted">{k}</dt>
                <dd className="tabular mt-0.5 text-sm font-semibold text-fg">{v}</dd>
              </div>
            ))}
          </dl>

          <section>
            <h3 className="mb-1.5 text-sm font-semibold text-fg">Summary</h3>
            <p className="text-sm leading-relaxed text-fg">
              <Cited text={memo.summary} onOpen={setSection} />
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-fg">Key metrics</h3>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
              {Object.entries(memo.key_metrics).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-fg-muted">{METRIC_LABEL[k] ?? k}</dt>
                  <dd className="tabular text-13 font-medium text-fg">{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          <div className="grid gap-6 md:grid-cols-2">
            {LISTS.map((l) => (
              <section key={l.key}>
                <h3 className="mb-1.5 text-sm font-semibold text-fg">{l.title}</h3>
                <ul className="list-disc space-y-1.5 pl-5 text-13 text-fg marker:text-fg-muted">
                  {memo[l.key].map((t) => (
                    <li key={t}>
                      <Cited text={t} onOpen={setSection} />
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-fg">Policy citations</h3>
            <ul className="flex flex-wrap gap-2">
              {memo.citations.map((c) => (
                <li key={c.section}>
                  <button
                    type="button"
                    onClick={() => setSection(c.section)}
                    className="rounded-full border border-edge bg-panel px-2.5 py-1 text-xs text-fg hover:border-primary hover:text-primary"
                  >
                    <span className="tabular font-semibold">§{c.section}</span> {c.title}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </article>
      </Card>

      <PolicySheet section={section} onClose={() => setSection(null)} />
      <Dialog
        open={!!preview}
        onOpenChange={(o) => {
          if (!o && preview) {
            URL.revokeObjectURL(preview);
            setPreview(null);
          }
        }}
        title="Credit memo PDF"
        className="max-w-4xl"
      >
        {preview && <iframe title="Credit memo PDF" src={preview} className="h-[70vh] w-full rounded-control border border-edge" />}
      </Dialog>
    </>
  );
}
