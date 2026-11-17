# Users

Four personas use UdyamPulse. All four exist as demo logins (password `demo123`). ✅ Done · 🟡 Partial · 🔭 Future.

## Personas

| Persona | Login | Goals | Pain points today |
|---|---|---|---|
| **Relationship Manager (RM)**, branch or zonal hub | `rm1` (hub), `rm3` (Morbi branch) | Bring good MSME loans in quickly; spot trouble in their book early | Collecting paper statements; stale data; learns of stress only at SMA-1/2; alerts with no "why" |
| **Credit Officer** | `co1` | Decide fast and defensibly, within policy | Rewriting the same memo; checking policy clauses by hand; numbers they cannot trace |
| **Risk Head** | `risk1` | See portfolio risk, prove models are fair, explainable and auditable | Quarterly, lagging views; model-risk questions from auditors and regulators |
| **MSME owner** (e.g. Sharma Auto Components, Ludhiana) | `sharma` (and `msme2`) | Get working capital without property collateral; know where they stand | Rejected without reasons; collateral demands; long waits; English-only, jargon-heavy apps |

Beneficiaries beyond the users:
- **Lenders:** faster decisions and earlier warnings.
- **MSMEs:** credit based on production rather than property.
- **MSME employees:** jobs kept when stress is caught early.
- **The economy:** a smaller credit gap.

## Needs → features

| Need | Feature | Status |
|---|---|---|
| RM: score an applicant without chasing paper | Consented data pull (mock Account Aggregator) → Factory Health Score with 5 plain-language reasons | ✅ |
| RM: know which accounts are slipping, and why | Early-warning alerts with severity, reasons and next-best action; an alert drawer with history and outcome logging | ✅ |
| Credit officer: a defensible memo fast | Credit-memo agent with policy citations, number guard and PDF; the decision stays with the officer | ✅ |
| Credit officer: test "what if" | What-if simulator (read-only, labelled as a simulation) | ✅ |
| Risk head: portfolio view | Cockpit: heatmap by cluster and sector, band migration, alert queue, playable simulated clock | ✅ |
| Risk head: model governance | Model inventory, fairness and drift, Data & Models provenance, audit trail with hash-chain verification, AI usage log, compliance map | ✅ |
| MSME owner: understand readiness in their language | MSME app with score, helping and hurting factors, cash-flow forecast, 90-day plan, in English or Hindi | ✅ |
| MSME owner: control over data | Consent view, revocation, my-data view and erasure request | ✅ |
| MSME owner: updates without logging in | WhatsApp-style notifications (mock channel, English and Hindi) | 🟡 Mock channel only |
| RM: works on a phone in the field | Responsive layout; PWA shell caches built assets | 🟡 |

## Journeys

1. **Onboard and decide (RM → credit officer):** open the application → request consent and pull data → run
   scoring → draft the memo → request review → the credit officer approves or rejects with a comment →
   disbursed and monitored.
2. **Early warning (RM / risk head):** the simulated clock advances → the batch flags stress (for the hero:
   e-way bills −42%, kWh −32%) → an alert with reasons and an action → the RM logs a visit or call and the
   outcome.
3. **MSME owner:** see the readiness score → what helps and what hurts → tick off 90-day plan steps → switch to
   Hindi → revoke consent, after which pulls are blocked.
4. **Governance (risk head):** model card metrics with CIs → fairness and drift → Data & Models provenance →
   verify the audit chain → consent ledger → AI usage.

## Accessibility and inclusion

| Need | What we do | Status |
|---|---|---|
| Low literacy, regional language | Hindi for the MSME app, plain-language reasons, icons beside every status | ✅ (Hindi) / 🔭 more languages, voice |
| Screen readers and keyboard | WCAG 2.2 AA contrast checked in CI; axe checks in every Playwright run; keyboard shortcuts; text alternatives on charts | ✅ |
| Low connectivity | Light bundle; PWA caches built assets; WhatsApp-style updates | 🟡 |
| Colour vision | Status always carries an icon and a label, never colour alone | ✅ |
| Dark or bright environments | Light and dark themes, both tested | ✅ |
