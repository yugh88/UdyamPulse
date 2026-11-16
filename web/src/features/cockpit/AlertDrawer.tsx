import { useMutation } from "@tanstack/react-query";
import { ArrowRight, CircleCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { AiLabel, Badge, Button, Field, Select, SeverityPill, Sheet, Textarea, Timeline, Tooltip } from "../../components/ui";
import { post } from "../../lib/api";
import { inr } from "../../lib/format";
import { monthLabel } from "../../lib/time";
import type { AlertRow } from "../../lib/types";

const ACTIONS = ["call", "visit", "limit review", "visit + limit review", "restructure", "no action"] as const;
const OUTCOMES = ["monitoring", "resolved", "escalated", "no contact"] as const;
export const RULE_LABEL: Record<string, string> = {
  order_loss: "Order loss",
  cash_squeeze: "Cash squeeze",
  buyer_risk: "Buyer risk",
  diversion: "Possible diversion",
  compliance_slip: "Compliance slip",
  anomaly: "Unusual pattern",
};

export function AlertDrawer({ alert, canAct, onClose, onDone }: { alert: AlertRow | null; canAct: boolean; onClose: () => void; onDone: () => void }) {
  const [action, setAction] = useState<string>("call");
  const [outcome, setOutcome] = useState<string>("monitoring");
  const [note, setNote] = useState("");
  useEffect(() => {
    if (alert) {
      setAction(ACTIONS.includes(alert.next_best_action as (typeof ACTIONS)[number]) ? alert.next_best_action : "call");
      setOutcome("monitoring");
      setNote("");
    }
  }, [alert]);

  const log = useMutation({
    mutationFn: () => post(`/alerts/${alert!.id}/action`, { action, note, outcome }),
    onSuccess: () => {
      toast.success(`Action logged for ${alert!.name}: ${action}`);
      onDone();
      onClose();
    },
    onError: (e) => toast.error(`Could not log the action: ${(e as Error).message}`),
  });

  return (
    <Sheet
      open={!!alert}
      onOpenChange={(o) => !o && onClose()}
      title={alert ? alert.name : "Alert"}
      description={alert ? `${alert.cluster} · ${alert.sector} · exposure ${inr(alert.exposure)}` : undefined}
      className="max-w-lg"
    >
      {alert && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityPill severity={alert.severity} />
            <Badge>{monthLabel(alert.month)}</Badge>
            <Badge>
              {alert.days_open} day{alert.days_open === 1 ? "" : "s"} open
            </Badge>
            <Badge>{alert.owner ? `Owner: ${alert.owner}` : "Unassigned"}</Badge>
            {alert.acknowledged_by && (
              <Badge tone="info" icon={<CircleCheck className="h-3 w-3" aria-hidden />}>
                Acknowledged by {alert.acknowledged_by}
              </Badge>
            )}
          </div>

          <section>
            <h3 className="mb-2 text-sm font-semibold text-fg">Next-best action</h3>
            <p className="flex items-center gap-2 rounded-control bg-primary-tint px-3 py-2.5 text-sm font-medium text-fg">
              <ArrowRight className="h-4 w-4 shrink-0 text-primary" aria-hidden />
              <span className="first-letter:uppercase">{alert.next_best_action}</span>
            </p>
          </section>

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-fg">RM briefing</h3>
              <AiLabel />
            </div>
            <p className="text-sm leading-relaxed text-fg">{alert.briefing}</p>
          </section>

          <section>
            <h3 className="mb-3 text-sm font-semibold text-fg">Reason timeline</h3>
            <Timeline
              items={alert.timeline.map((t) => ({
                id: t.id,
                tone: t.severity === "high" ? "danger" : t.severity === "medium" ? "warning" : "info",
                title: (
                  <span className="inline-flex flex-wrap items-center gap-2">
                    {monthLabel(t.month)} <SeverityPill severity={t.severity} />
                    {t.id === alert.id && <Badge tone="primary">this alert</Badge>}
                  </span>
                ),
                meta: t.status === "ACTIONED" ? `actioned: ${t.action_taken}` : `raised ${t.raised_on}`,
                body: (
                  <ul className="list-disc space-y-0.5 pl-4">
                    {t.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                ),
              }))}
            />
          </section>

          {alert.status === "ACTIONED" ? (
            <section className="rounded-control bg-success-tint px-3 py-2.5 text-sm text-fg">
              <p className="font-medium">
                Actioned by {alert.actioned_by}: {alert.action_taken}
                {alert.outcome ? ` · outcome: ${alert.outcome}` : ""}
              </p>
              {alert.action_note && <p className="mt-1 text-fg-muted">“{alert.action_note}”</p>}
            </section>
          ) : (
            <section>
              <h3 className="mb-3 text-sm font-semibold text-fg">Log action</h3>
              <fieldset disabled={!canAct} className="space-y-3 disabled:opacity-60">
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
                <Field label="Note" hint="What you found and agreed with the borrower.">
                  <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
                </Field>
                <Tooltip content={canAct ? null : "Only relationship managers and credit officers log actions."}>
                  <span tabIndex={canAct ? -1 : 0} className="inline-block">
                    <Button variant="primary" loading={log.isPending} onClick={() => log.mutate()}>
                      Log action
                    </Button>
                  </span>
                </Tooltip>
              </fieldset>
              {!canAct && <p className="mt-2 text-xs text-fg-muted">Only relationship managers and credit officers log actions.</p>}
            </section>
          )}

          <Link to={`/console/${alert.application_id}`} className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            Open the account <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
      )}
    </Sheet>
  );
}
