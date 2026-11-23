import { Banknote, CircleCheck, CircleDot, CircleX, FileText, Gavel, Lock } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Dialog, EmptyState, Field, Input, Textarea, Tooltip } from "../../components/ui";
import { cn } from "../../lib/cn";
import { inr, pct, rupees } from "../../lib/format";
import { dateTime } from "../../lib/time";
import { dejargon, plainDetail } from "../../lib/reasons";
import type { AppDetail } from "../../lib/types";
import { Cited, PolicyChips } from "./Memo";

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

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control bg-panel-2 px-5 py-4">
      <p className="label-caps">{label}</p>
      <p className="tabular mt-1.5 text-2xl font-bold tracking-[-0.5px] text-fg">{value}</p>
    </div>
  );
}

/** Left card: the memo in one screen. Strengths, risks paired with how they are managed, and the clauses cited. */
export function MemoSummary({ app, onOpenPolicy }: { app: AppDetail; onOpenPolicy: (section: string) => void }) {
  const memo = app.memo;
  const [more, setMore] = useState(false);
  if (!memo)
    return (
      <Card>
        <EmptyState
          icon={<FileText className="h-6 w-6" aria-hidden />}
          title="No memo yet"
          description="The memo agent drafts it after scoring. The decision opens once the memo is ready."
        />
      </Card>
    );
  // The two strongest of each, in plain words; the full memo is one click away (and on the Credit memo tab).
  // Lines built from a score reason are restated with that reason's plain detail; the rest lose their jargon.
  const reasons = app.score_detail?.reasons ?? [];
  const plain = (t: string) => {
    const r = reasons.find((x) => t.startsWith(x.text));
    return r ? dejargon(plainDetail(r) + t.slice(r.text.length)) : dejargon(t);
  };
  const strengths = memo.strengths.map(plain);
  const risks = memo.risks.map(plain);
  const mitigants = memo.mitigants.map(dejargon);
  const hidden = Math.max(0, strengths.length - 2) + Math.max(0, risks.length - 2);
  return (
    <Card title="Memo summary" description="Drafted by the memo agent · every number comes from the scoring and policy engines">
      <div className="grid gap-4 sm:grid-cols-3">
        <Tile label="Recommended limit" value={memo.recommended_limit_display} />
        <Tile label="Pricing" value={memo.pricing_band} />
        <Tile label="Risk of default · 12 months" value={pct(app.pd_12m, 1)} />
      </div>
      <section className="mt-6">
        <h3 className="text-base font-[650] text-fg">Strengths</h3>
        <ul className="mt-3 space-y-2.5">
          {strengths.slice(0, more ? undefined : 2).map((t) => (
            <li key={t} className="flex gap-2.5 text-sm text-fg">
              <CircleCheck className="mt-0.5 h-[18px] w-[18px] shrink-0 text-success" aria-hidden />
              <span>
                <Cited text={t} onOpen={onOpenPolicy} />
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section className="mt-6">
        <h3 className="text-base font-[650] text-fg">Risks & how to manage them</h3>
        <ul className="mt-3 space-y-2.5">
          {risks.slice(0, more ? undefined : 2).map((t, i) => (
            <li key={t} className="flex gap-2.5 text-sm text-fg">
              <CircleDot className="mt-0.5 h-[18px] w-[18px] shrink-0 text-warning" aria-hidden />
              <span>
                <Cited text={t} onOpen={onOpenPolicy} />
                {mitigants[i] && (
                  <>
                    <span className="text-fg-muted"> → </span>
                    <Cited text={mitigants[i]} onOpen={onOpenPolicy} />
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>
      {hidden > 0 && (
        <button type="button" onClick={() => setMore((m) => !m)} aria-expanded={more} className="mt-4 text-13 font-semibold text-primary hover:underline">
          {more ? "Show less" : `Show ${hidden} more`}
        </button>
      )}
      {memo.citations.length > 0 && (
        <section className="mt-6 flex flex-wrap items-center gap-3">
          <h3 className="label-caps">Policy cited</h3>
          <PolicyChips citations={memo.citations} onOpen={onOpenPolicy} />
        </section>
      )}
    </Card>
  );
}

/** Right card: only a credit officer can decide. Choose, set the limit, justify, confirm against the KFS preview. */
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
        className="border-2 border-primary"
        title="Decision"
        actions={
          <Badge tone={approved ? "success" : "danger"} icon={approved ? <CircleCheck className="h-3.5 w-3.5" aria-hidden /> : <CircleX className="h-3.5 w-3.5" aria-hidden />}>
            {approved ? "Approved" : "Rejected"}
          </Badge>
        }
      >
        <p className="text-sm text-fg">“{app.decision_comment}”</p>
        <p className="mt-1 text-13 text-fg-muted">
          Decided by {app.decided_by}
          {app.decided_at ? ` on ${dateTime(app.decided_at)}` : ""}
          {approved && app.sanctioned_limit ? ` · sanctioned ${inr(app.sanctioned_limit)}` : ""}
        </p>
        {app.kfs && (
          <div className="mt-5">
            <h3 className="mb-2 text-sm font-semibold text-fg">Key Fact Statement</h3>
            <Kfs kfs={app.kfs} />
          </div>
        )}
        {approved && app.state === "DECIDED" && (role === "credit_officer" || role === "rm") && (
          <Button variant="primary" size="lg" className="mt-5 w-full" loading={disbursing} onClick={onDisburse} icon={<Banknote className="h-4 w-4" aria-hidden />}>
            Disburse via LOS
          </Button>
        )}
        {app.disbursement_ref && (
          <p className="mt-4 text-13 text-fg-muted">
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
      className="border-2 border-primary"
      title="Your decision"
      description="Only a credit officer can decide. AI only recommends."
      actions={
        locked ? (
          <Tooltip content={lockedWhy}>
            <span tabIndex={0}>
              <Badge tone="neutral" icon={<Lock className="h-3 w-3" aria-hidden />}>
                Read-only
              </Badge>
            </span>
          </Tooltip>
        ) : undefined
      }
    >
      {locked && (
        <p className="mb-4 flex items-start gap-2 rounded-control bg-panel-2 px-3 py-2.5 text-13 text-fg-muted">
          <Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {lockedWhy}
        </p>
      )}
      <fieldset disabled={locked} className="space-y-5 disabled:opacity-60">
        <div role="radiogroup" aria-label="Decision" className="grid grid-cols-2 gap-3">
          {(
            [
              ["APPROVED", "Approve", CircleCheck],
              ["REJECTED", "Reject", CircleX],
            ] as const
          ).map(([value, label, Icon]) => {
            const on = choice === value;
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setChoice(value)}
                className={cn(
                  "flex h-24 flex-col items-center justify-center gap-2 rounded-card border-2 text-base font-semibold transition-colors duration-150 disabled:cursor-not-allowed",
                  on
                    ? value === "APPROVED"
                      ? "border-primary bg-primary-tint text-primary"
                      : "border-danger bg-danger-tint text-danger"
                    : "border-edge-2 bg-panel text-fg-muted hover:text-fg",
                )}
              >
                <Icon className="h-6 w-6" aria-hidden />
                {label}
              </button>
            );
          })}
        </div>

        {choice === "APPROVED" && (
          <Field
            label="Sanctioned limit"
            required
            error={touched ? limitError : null}
            hint={
              <>
                {limitNum > 0 && `${inr(limitNum)}`}
                {app.recommended_limit != null && (
                  <>
                    {limitNum > 0 ? " · " : ""}memo recommends {inr(app.recommended_limit)}
                  </>
                )}
                {aboveRecommended && <span className="font-medium text-warning"> · above the recommended limit</span>}
              </>
            }
          >
            <Input
              inputMode="numeric"
              className="tabular h-12 text-base font-semibold"
              value={limitNum > 0 ? rupees(limitNum) : limit}
              onChange={(e) => setLimit(e.target.value.replace(/[^\d]/g, ""))}
            />
          </Field>
        )}

        <Field label="Comment" required error={touched ? commentError : null} hint="Recorded in the audit trail with your name.">
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={3}
            placeholder={choice === "APPROVED" ? "Why this limit and these conditions" : "Main reasons for declining"}
          />
        </Field>

        {choice === "APPROVED" && (
          <p className="flex items-start gap-2.5 rounded-control bg-info-tint px-4 py-3 text-13 text-info">
            <FileText className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            The Key Fact Statement will be shown to the borrower before signing.
          </p>
        )}

        <Button
          variant={choice === "APPROVED" ? "primary" : "danger"}
          size="lg"
          className="w-full"
          icon={<Gavel className="h-4 w-4" aria-hidden />}
          onClick={() => {
            setTouched(true);
            if (!limitError && !commentError) setConfirm(true);
          }}
        >
          {choice === "APPROVED" ? "Confirm approval" : "Confirm rejection"}
        </Button>
      </fieldset>

      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title={choice === "APPROVED" ? "Approve this application?" : "Reject this application?"}
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
              {choice === "APPROVED" ? "Approve and issue KFS" : "Reject application"}
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
