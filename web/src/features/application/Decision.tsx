import { BadgeCheck, Ban, Banknote, Lock } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Dialog, Field, Input, Textarea, Tooltip } from "../../components/ui";
import { cn } from "../../lib/cn";
import { inr, rupees } from "../../lib/format";
import { dateTime } from "../../lib/time";
import type { AppDetail } from "../../lib/types";

const KFS_LABEL: Record<string, string> = {
  lender: "Lender",
  technology_service_provider: "Technology service provider",
  product: "Product",
  sanctioned_limit: "Sanctioned limit",
  interest: "Interest",
  fees: "Fees",
  apr: "Annual percentage rate",
  tenor: "Tenor",
  disbursal: "Disbursal",
  cooling_off: "Cooling-off",
  grievance: "Grievance redressal",
  ai_disclosure: "AI disclosure",
  status: "Status",
};

export function Kfs({ kfs }: { kfs: Record<string, string> }) {
  return (
    <dl className="divide-y divide-edge rounded-control border border-edge">
      {Object.entries(kfs).map(([k, v]) => (
        <div key={k} className="grid grid-cols-[11rem_1fr] gap-3 px-3 py-2 text-13">
          <dt className="text-fg-muted">{KFS_LABEL[k] ?? k}</dt>
          <dd className="text-fg">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export interface DecisionInput {
  decision: "APPROVED" | "REJECTED";
  comment: string;
  sanctioned_limit?: number;
}

/** Credit-officer decision: choose, justify, preview the Key Fact Statement, then confirm. */
export function DecisionPanel({
  app,
  role,
  deciding,
  disbursing,
  onDecide,
  onDisburse,
}: {
  app: AppDetail;
  role: string;
  deciding: boolean;
  disbursing: boolean;
  onDecide: (d: DecisionInput) => Promise<unknown>;
  onDisburse: () => void;
}) {
  const [choice, setChoice] = useState<"APPROVED" | "REJECTED">(app.band === "HIGH_RISK" ? "REJECTED" : "APPROVED");
  const [limit, setLimit] = useState<string>(app.recommended_limit ? String(app.recommended_limit) : "");
  const [comment, setComment] = useState("");
  const [touched, setTouched] = useState(false);
  const [confirm, setConfirm] = useState(false);

  if (app.decision) {
    const approved = app.decision === "APPROVED";
    return (
      <Card
        title="Decision"
        actions={
          <Badge tone={approved ? "success" : "danger"} icon={approved ? <BadgeCheck className="h-3.5 w-3.5" aria-hidden /> : <Ban className="h-3.5 w-3.5" aria-hidden />}>
            {approved ? "Approved" : "Rejected"}
          </Badge>
        }
      >
        <p className="text-sm text-fg">“{app.decision_comment}”</p>
        <p className="mt-1 text-xs text-fg-muted">
          Decided by {app.decided_by}
          {app.decided_at ? ` on ${dateTime(app.decided_at)}` : ""}
          {approved && app.sanctioned_limit ? ` · sanctioned ${inr(app.sanctioned_limit)}` : ""}
        </p>
        {app.kfs && (
          <div className="mt-4">
            <h3 className="mb-2 text-13 font-semibold text-fg">Key Fact Statement</h3>
            <Kfs kfs={app.kfs} />
          </div>
        )}
        {approved && app.state === "DECIDED" && (role === "credit_officer" || role === "rm") && (
          <Button variant="primary" className="mt-4" loading={disbursing} onClick={onDisburse} icon={<Banknote className="h-4 w-4" aria-hidden />}>
            Disburse via LOS
          </Button>
        )}
        {app.disbursement_ref && (
          <p className="mt-3 text-13 text-fg-muted">
            Disbursed on {app.disbursed_on} · reference <span className="tabular font-medium text-fg">{app.disbursement_ref}</span> · directly to the borrower's own account
          </p>
        )}
      </Card>
    );
  }

  const isOfficer = role === "credit_officer";
  const ready = app.state === "MEMO_DRAFTED";
  const lockedWhy = !isOfficer ? "Only a credit officer can approve or reject. The system only recommends." : !ready ? "Generate the credit memo before deciding." : null;
  const locked = lockedWhy !== null;

  const limitNum = Number(limit);
  const limitError = choice === "APPROVED" && (!limit || !(limitNum > 0)) ? "Enter the sanctioned limit in rupees" : null;
  const commentError = comment.trim().length < 3 ? "A justification is mandatory (at least 3 characters)" : null;
  const aboveRecommended = choice === "APPROVED" && app.recommended_limit != null && limitNum > app.recommended_limit;

  const previewKfs: Record<string, string> = {
    product: "Working-capital cash credit (MSME)",
    sanctioned_limit: rupees(limitNum),
    interest: `${app.pricing_band ?? "–"} (EBLR-linked, floating)`,
    tenor: "12 months, renewable on review",
    disbursal: "Directly to the borrower's own bank account; no pass-through accounts",
    ai_disclosure: "AI-assisted analysis was used; the decision is made by an authorised credit officer",
  };

  return (
    <Card
      title="Decision"
      description="Final decision by the credit officer. The memo is a recommendation."
      actions={
        locked ? (
          <Tooltip content={lockedWhy}>
            <span tabIndex={0}>
              <Badge tone="neutral" icon={<Lock className="h-3 w-3" aria-hidden />}>
                Locked
              </Badge>
            </span>
          </Tooltip>
        ) : undefined
      }
    >
      {locked && <p className="mb-4 rounded-control bg-panel-2 px-3 py-2 text-13 text-fg-muted">{lockedWhy}</p>}
      <fieldset disabled={locked} className="space-y-4 disabled:opacity-60">
        <div role="radiogroup" aria-label="Decision" className="grid grid-cols-2 gap-2">
          {(
            [
              ["APPROVED", "Approve", BadgeCheck],
              ["REJECTED", "Reject", Ban],
            ] as const
          ).map(([value, label, Icon]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={choice === value}
              onClick={() => setChoice(value)}
              className={cn(
                "flex h-10 items-center justify-center gap-2 rounded-control border text-sm font-medium transition-colors disabled:cursor-not-allowed",
                choice === value
                  ? value === "APPROVED"
                    ? "border-success bg-success-tint text-success"
                    : "border-danger bg-danger-tint text-danger"
                  : "border-edge-strong bg-panel text-fg-muted hover:text-fg",
              )}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </button>
          ))}
        </div>

        {choice === "APPROVED" && (
          <Field
            label="Sanctioned limit (₹)"
            required
            error={touched ? limitError : null}
            hint={
              limitNum > 0 ? (
                <>
                  {rupees(limitNum)} · {inr(limitNum)}
                  {app.recommended_limit != null && <> · memo recommends {inr(app.recommended_limit)}</>}
                  {aboveRecommended && <span className="font-medium text-warning"> · above the recommended limit</span>}
                </>
              ) : app.recommended_limit != null ? (
                `Memo recommends ${inr(app.recommended_limit)}`
              ) : undefined
            }
          >
            <Input inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value.replace(/[^\d]/g, ""))} />
          </Field>
        )}

        <Field label="Comment" required error={touched ? commentError : null} hint="Recorded in the audit trail with your name.">
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            placeholder={choice === "APPROVED" ? "Why this limit and these conditions" : "Main reasons for declining"}
          />
        </Field>

        <Button
          variant="primary"
          onClick={() => {
            setTouched(true);
            if (!limitError && !commentError) setConfirm(true);
          }}
        >
          {choice === "APPROVED" ? "Review Key Fact Statement" : "Review rejection"}
        </Button>
      </fieldset>

      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title={choice === "APPROVED" ? "Confirm approval" : "Confirm rejection"}
        description={`${app.name} · application #${app.id}`}
        footer={
          <>
            <Button onClick={() => setConfirm(false)} disabled={deciding}>
              Back
            </Button>
            <Button
              variant={choice === "APPROVED" ? "primary" : "danger"}
              loading={deciding}
              onClick={async () => {
                try {
                  await onDecide({ decision: choice, comment: comment.trim(), sanctioned_limit: choice === "APPROVED" ? limitNum : undefined });
                  setConfirm(false);
                } catch {
                  /* the page shows the error toast */
                }
              }}
            >
              {choice === "APPROVED" ? "Confirm approval" : "Confirm rejection"}
            </Button>
          </>
        }
      >
        {choice === "APPROVED" ? (
          <>
            <p className="mb-3 text-13 text-fg-muted">Key Fact Statement preview. The lender's LOS issues the final statement with the APR and fees in rupees.</p>
            <Kfs kfs={previewKfs} />
          </>
        ) : (
          <p className="text-sm text-fg">
            The MSME will be told the application was not approved, shown the main reasons and a 90-day improvement plan, and can request a human review.
          </p>
        )}
        <p className="mt-4 text-13 text-fg">
          <span className="text-fg-muted">Your comment:</span> “{comment.trim()}”
        </p>
      </Dialog>
    </Card>
  );
}
