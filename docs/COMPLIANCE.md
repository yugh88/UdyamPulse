# Compliance and security by design

UdyamPulse is a **technology service provider (TSP)** to a regulated lender (the "RE"). This page maps each
regulatory expectation to the control that implements it and the test or artefact that proves it.

> Prototype status: controls are implemented against synthetic data. A production deployment needs the RE's
> legal review, a DPIA, and independent model validation.

## RBI Digital Lending Directions, 2025

| Expectation | How UdyamPulse meets it | Evidence |
|---|---|---|
| RE owns the credit decision | Only the `credit_officer` role can call `POST /applications/{id}/decision`; a written comment is mandatory. The system only recommends. | `api/routers/applications.py`, `tests/test_api_roles_consent.py::test_full_journey_roles_and_audit` |
| Disbursal directly to borrower's account | LOS stub records "direct to borrower's own account; no pass-through"; UdyamPulse never holds funds. | `agents/orchestrator.py::disburse` |
| Key Fact Statement before execution | KFS stub generated on approval and shown on the approval screen (APR computed by the RE's LOS). | `key_fact_statement()`, console "Key Fact Statement" card |
| Credit-bureau reporting & grievance redressal stay with the RE | KFS names the RE's grievance officer and RBI Integrated Ombudsman; no bureau reporting in the TSP. | KFS stub |
| Collect only necessary data; no biometrics | Consent artefact lists the exact FI types; `/msme/{id}/my-data` lists categories *not* collected (biometrics, contacts, location). | `agents/providers/consent.py`, `api/routers/msme.py` |
| Data stored in India | `assert_data_residency()` refuses to start if `UP_DATA_REGION` is not an India region (prod: Azure Central India / South India). | `core/settings.py`, `api/main.py` |

## DPDP Act 2023 / DPDP Rules 2025

| Expectation | Control | Evidence |
|---|---|---|
| Notice stating the purpose | Consent artefact purpose: *"MSME working-capital underwriting and loan monitoring"*; shown in the console and the MSME app. | `PURPOSE` in `consent.py`, MSME app → Consent tab |
| Consent ledger | Append-only `consent_ledger`: `GRANTED`, `DATA_PULL`, `PULL_BLOCKED`, `REVOKED`, `DELETION_JOB`, `EXPIRED`. | `GET /applications/{id}/consent-ledger` |
| Withdrawal as easy as giving consent | One-tap **Revoke** in the MSME app. Revocation blocks every future pull (scoring, memo, monitoring) and triggers a deletion job for held snapshots. | `tests/test_api_roles_consent.py::test_revoking_consent_blocks_new_pulls` |
| Retention limits | Snapshots deleted on revocation; retention policy surfaced in `/my-data`. | `DataSnapshot`, `my_data()` |
| Data-principal rights | `GET /msme/{id}/my-data` (access) and `POST /msme/{id}/erasure-request` (erasure) stubs, both audited. | `api/routers/msme.py` |

## RBI FREE-AI principles (Framework for Responsible and Ethical Enablement of AI)

| Principle | Control |
|---|---|
| Explainability | Every score carries TreeSHAP top-5 reasons in plain language + pillar contributions in score points (`ml/scoring.py`). |
| Human in the loop | Recommendations only; decision endpoint restricted to credit officers; "Recommendation" language in memos. |
| Disclosure of AI use | Every AI output in the UI carries *"AI-generated recommendation · final decision by credit officer"*; KFS states AI-assisted analysis was used. |
| Right to challenge | **Request review** button in the MSME app → `POST /applications/{id}/review-request`, flagged in the console. |
| No invented facts | Number guard rejects any LLM output containing numbers not in the structured facts (`agents/guard.py`, unit-tested). |
| Model inventory & card | `GET /model` (risk role) + `ml/MODEL_CARD.md` with data, metrics, limitations and fairness. |
| Fairness | Per-training-run disparity check across sectors and micro vs small: adverse-impact and equal-opportunity ratios (`ml/reports/fairness.json`). No protected attributes exist in the data. |
| Drift monitoring | PSI on score and top features between training and recent periods (`ml/reports/drift.json`). |
| Audit trail | `audit_log` records agent, tool, PII-masked inputs, SHA-256 of outputs, user, role and time for every API action and agent tool call; readable only by the `risk` role. |

## Security

| Control | Prototype | Production |
|---|---|---|
| Authentication | JWT (HS256) with roles `rm`, `credit_officer`, `risk`, `msme` | Microsoft Entra ID (OIDC) |
| Authorisation | `require_roles()` per endpoint; MSME users restricted to their own factory | Same + APIM policies |
| Secrets | `.env` (git-ignored); `.env.example` has no secrets | Azure Key Vault + managed identity |
| PII in logs | `mask_pii()` masks names, phones, emails, PAN before audit writes | Same + Purview classification |
| Transport | Optional HTTPS via Caddy (`docker compose --profile https up`) | Front Door / App Gateway TLS |
| Dependency scanning | `pip-audit` and `npm audit` in GitHub Actions | Defender for DevOps |
| Passwords | PBKDF2-SHA256, 120k iterations, per-user salt | Entra ID |
