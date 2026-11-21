import { useQuery } from "@tanstack/react-query";
import { Bot, ChevronDown } from "lucide-react";
import { useState } from "react";
import { Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { cn } from "../../lib/cn";
import type { Memo } from "../../lib/types";

interface AuditRow {
  id: number;
  ts: string;
  user: string;
  agent: string;
  tool: string;
  action: string;
}

/** How the memo was made. The risk head sees the real tool-call trace from the audit chain, with timings; other roles
 * see the steps the memo itself records (engine → policy → writer → officer). Collapsed by default. */
export function AgentTrace({ applicationId, memo, canAudit }: { applicationId: number; memo: Memo; canAudit: boolean }) {
  const [open, setOpen] = useState(false);
  const audit = useQuery({
    queryKey: ["audit", applicationId],
    queryFn: () => api<AuditRow[]>(`/audit?application_id=${applicationId}&limit=60`),
    enabled: open && canAudit,
  });
  const template = memo.llm_provider === "template";
  const steps = [
    { who: "Planner", what: "Orchestrator checked consent and the application state, then called the tools in order." },
    { who: "Tool · scoring engine", what: "Score, band, 12-month risk of default and the top reasons. Every number in the memo comes from here." },
    { who: "Tool · policy engine", what: `Limit, pricing and covenants from the bank's credit policy; ${memo.citations.length} clauses cited.` },
    {
      who: "Memo writer",
      what: template
        ? "Deterministic template, run locally with no external API."
        : `${memo.llm_provider} wrote the prose only; a number guard rejects any number that is not in the engine's facts.`,
    },
    { who: "Review", what: "The credit officer reads the memo and decides. The AI only recommends." },
  ];
  const rows = audit.data ? [...audit.data].reverse() : [];
  const t0 = rows.length ? new Date(rows[0].ts).getTime() : 0;

  return (
    <section className="rounded-control border border-edge">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left text-sm font-semibold text-fg hover:bg-panel-2/60"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-purple-tint text-purple" aria-hidden>
          <Bot className="h-4 w-4" />
        </span>
        <span className="flex-1">Agent trace: how this memo was made</span>
        {memo.generated_in_ms != null && <span className="tabular text-13 font-normal text-fg-muted">{memo.generated_in_ms} ms</span>}
        <ChevronDown className={cn("h-4 w-4 text-fg-muted transition-transform duration-150", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="border-t border-edge px-4 py-3">
          {canAudit ? (
            audit.isLoading ? (
              <Skeleton className="h-32" />
            ) : audit.isError ? (
              <p className="text-13 text-danger">Could not load the trace: {(audit.error as Error).message}</p>
            ) : (
              <ol className="space-y-1.5">
                {rows.map((r) => (
                  <li key={r.id} className="grid grid-cols-[4.5rem_1fr] gap-3 text-13">
                    <span className="tabular text-right text-fg-muted">+{((new Date(r.ts).getTime() - t0) / 1000).toFixed(2)} s</span>
                    <span className="text-fg">
                      <span className="font-medium">{r.agent}</span> · {r.tool} · {r.action}
                      <span className="text-fg-muted"> ({r.user})</span>
                    </span>
                  </li>
                ))}
              </ol>
            )
          ) : (
            <>
              <ol className="space-y-2.5">
                {steps.map((s, i) => (
                  <li key={s.who} className="flex gap-3 text-13">
                    <span className="tabular flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-purple-tint text-xs font-semibold text-purple">{i + 1}</span>
                    <span>
                      <span className="font-semibold text-fg">{s.who}: </span>
                      <span className="text-fg-muted">{s.what}</span>
                    </span>
                  </li>
                ))}
              </ol>
              <p className="mt-3 text-xs text-fg-muted">The full tool-call trace with timings is on the audit chain, visible to the risk head.</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
