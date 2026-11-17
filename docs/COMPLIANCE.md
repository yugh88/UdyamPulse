# Compliance by design

UdyamPulse is a **technology service provider (TSP)** to a regulated lender, the "regulated entity" (RE). This
page maps each regulatory expectation to the control that implements it, and says plainly which items the
prototype implements and which are process items owned by the lender.

**Status:**
- ✅ Implemented in the prototype (tested)
- 🟡 Partly implemented, or stubbed
- 🏦 Lender process item: the RE owns it, and UdyamPulse supports it

The prototype runs on synthetic data. A production deployment needs the RE's legal review, a data protection
impact assessment (DPIA) and independent model validation.

## RBI Digital Lending Directions, 2025

| Expectation | How UdyamPulse meets it | Evidence | Status |
|---|---|---|---|
| The RE owns the credit decision | Only the `credit_officer` role can call `POST /v1/applications/{id}/decision`, with a mandatory comment; agents only recommend | `api/routers/applications.py`, `tests/test_api_roles_consent.py` | ✅ |
| Disbursal directly to the borrower's account | The LOS stub records "direct to borrower's own account; no pass-through"; UdyamPulse never holds funds | `agents/orchestrator.py` | 🟡 stub; the real LOS is 🏦 |
| Key Fact Statement before execution | KFS stub generated on approval and shown on the approval screen; the APR is computed by the RE's LOS | console "Key Fact Statement" card | 🟡 stub / 🏦 |
| Grievance redressal and bureau reporting stay with the RE | The KFS names the RE's grievance officer and the RBI Integrated Ombudsman; the TSP does no bureau reporting | KFS stub | 🏦 |
| Collect only necessary data; no biometrics, contacts or location | The consent artefact lists the exact data types; `/v1/msme/{id}/my-data` lists the categories not collected | `agents/providers/consent.py`, `api/routers/msme.py` | ✅ |
| Data stored in India | The app refuses to start outside an India region; production refuses `UP_DATA_REGION=local`; the Terraform design accepts only Indian regions | `core/settings.py`, `deploy/terraform/variables.tf` | ✅ (cloud design 🔭) |
| Due diligence on the TSP, and RE audit rights | Hash-chained audit trail, model card, threat model and an exportable audit log | `docs/THREAT_MODEL.md`, `ml/MODEL_CARD.md` | 🏦 supported |

## DPDP Act 2023 and DPDP Rules 2025

| Expectation | Control | Evidence | Status |
|---|---|---|---|
| Notice stating the purpose | Consent purpose "MSME working-capital underwriting and loan monitoring", shown in the console and the MSME app | `PURPOSE` in `consent.py`, MSME app → Consent | ✅ |
| Consent ledger | Append-only ledger: `GRANTED`, `DATA_PULL`, `PULL_BLOCKED`, `REVOKED`, `DELETION_JOB`, `EXPIRED` | `GET /v1/applications/{id}/consent-ledger` | ✅ |
| Withdrawal as easy as consent | One-tap revoke in the MSME app; every later pull is blocked and held snapshots are deleted | `tests/test_api_roles_consent.py::test_revoking_consent_blocks_new_pulls` | ✅ |
| Consent expiry | Expired consents are treated as inactive before any pull and recorded as `EXPIRED` | `agents/providers/consent.py` | ✅ |
| Data-principal rights | Access (`/my-data`) and erasure (`/erasure-request`), both audited | `api/routers/msme.py` | 🟡 erasure request recorded; fulfilment workflow 🏦 |
| Security safeguards | Field-level encryption, PII masking in logs, access control, hash-chained audit | `docs/SECURITY.md` | ✅ |
| Breach notification | Incident process with the RE (Data Protection Board, affected principals) | not in code | 🏦 |
| Retention limits | Snapshots deleted on revocation; retention policy shown in `/my-data`; record-retention periods are set by the RE | `DataSnapshot`, `my_data()` | 🟡 / 🏦 |

## Account Aggregator framework

| Expectation | Control | Status |
|---|---|---|
| Consent artefact (purpose, FI types, range, frequency, expiry) | Modelled field for field in the `consents` table and the consent screen | ✅ (mock AA) |
| The RE acts as the Financial Information User (FIU) | The partner bank registers as FIU; UdyamPulse processes on its behalf | 🏦 |
| Pull only under an active consent | Enforced before every pull; blocked pulls are logged | ✅ |
| Live AA integration (Sahamati-certified) | Provider interface in place (`UP_CONSENT_PROVIDER=sahamati_aa`); live connector not built | 🔭 |

## RBI FREE-AI and model risk

| Expectation | Control | Status |
|---|---|---|
| Explainability | SHAP top-5 reasons in plain language and pillar points on every score | ✅ |
| Human in the loop | Recommendations only; the decision endpoint is restricted to credit officers | ✅ |
| Disclosure of AI use | Every AI output is labelled "AI-generated recommendation · final decision by credit officer" | ✅ |
| Right to challenge | "Request review" → `POST /v1/applications/{id}/review-request` | ✅ |
| No invented facts | Number guard; template fallback | ✅ |
| Model inventory and card | `GET /v1/model`, `ml/MODEL_CARD.md` (synthetic, demo and real sections kept separate) | ✅ |
| Fairness and drift | Per-run disparity ratios; PSI drift | ✅ |
| Independent model validation and approval | The RE's model-risk function before production use | 🏦 |

Full mapping: `docs/RESPONSIBLE_AI.md`.

## Security

Summary in `docs/SECURITY.md`, STRIDE analysis in `docs/THREAT_MODEL.md`:
- argon2id passwords and short-lived tokens with rotating refresh cookies
- RBAC plus branch scope, and bank isolation with row-level security
- field encryption and a hash-chained audit trail
- rate limits and a CSP
- blocking dependency, secret and image scans

In production, Entra ID replaces the password step and Key Vault holds the secrets (🔭).
