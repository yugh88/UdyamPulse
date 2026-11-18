# Threat model

UdyamPulse holds consented operating and banking data of MSME borrowers, produces credit scores and memos,
and records credit decisions. This document lists what we protect, where trust changes hands, the threats
per component (STRIDE) and the control that answers each one, with the file or test that proves it. It
ends with the risks we know are still open.

All data in this repository is synthetic. Every control below is active in the local demo unless marked
**prod**, which means it is configured at deployment (Azure) and refused at start-up if missing
(`UP_ENV=production`, `core/settings.py: production_problems`).

## 1. Assets

| Asset | Why it matters | Where it lives |
|---|---|---|
| Consented financial data (GST, bank statements, e-way bills, power) | Personal and commercial data under DPDP 2023 and the AA framework | `data_snapshots.payload` (encrypted), lake |
| Personal data of staff and owners | DPDP | `users.display_name` (encrypted), notes |
| Credit decisions, memos, scores | Regulatory record (RBI Digital Lending Directions 2025), money moves on them | `applications`, `account_scores` |
| Audit trail | Evidence for regulators and disputes | `audit_log` (hash-chained) |
| Model and policy artefacts | Integrity of every score | image layer, `ml/artifacts`, `policy/` |
| Credentials and keys | Everything above | env / Azure Key Vault (prod) |

## 2. Trust boundaries

```
 Browser ──TLS──▶ Front door (nginx / Caddy / App Gateway WAF in prod)
                     │  CSP, frame-ancestors none, /metrics not proxied
                     ▼
                  API pods (FastAPI) ──▶ PostgreSQL (RLS, non-superuser role)
                     │        │      └─▶ Redis (cache, limits, queue; no source of truth)
                     │        └─▶ Outbox ─▶ relay ─▶ Dramatiq workers (same image, same checks)
                     └─▶ LLM provider (optional, prod: Azure OpenAI in Central India)
                     └─▶ Account Aggregator (prod: Sahamati FIU; local: mock)
```

Boundaries: (1) internet → front door, (2) front door → API, (3) API/worker → data stores, (4) API → external
AI and AA services, (5) one bank → another bank inside the same deployment.

## 3. STRIDE by component

### 3.1 Sign-in and sessions

| Threat | Control | Evidence |
|---|---|---|
| **S** Password guessing | argon2id (RFC 9106 parameters), login limited to 30/min per address, refresh too | `api/auth.py`, `api/middleware.py`, `tests/test_edge.py` |
| **S** Username probing by timing | Unknown users are checked against a real dummy hash; same error text | `tests/test_auth.py::test_unknown_user_and_wrong_password_look_the_same` |
| **S** Stolen access token | 15-minute lifetime, held in memory only (never localStorage) | `web/src/lib/api.ts`, e2e `a reload keeps the session ... without storing a token` |
| **S** Stolen refresh token | httpOnly, SameSite=Strict, Secure (prod) cookie; SHA-256 stored only; rotated on every use; replay revokes the whole family | `tests/test_auth.py::test_refresh_rotates_and_old_token_reuse_revokes_the_family` |
| **R** Denying a sign-in | `login`, `login_failed`, `logout`, `refresh_reuse_detected` audited | `api/routers/auth.py` |
| **E** Forged or retyped JWT | HS256 with a ≥32-char secret (prod check), `exp`/`sub`/`tid` required, `typ=access` enforced | `tests/test_auth.py::test_expired_or_wrong_type_access_token_is_rejected` |
| **T** CSRF on refresh/logout | SameSite=Strict cookie, same-origin API, CORS allow-list, no cookie auth on any other endpoint | `api/main.py` |

In production Microsoft Entra ID replaces the password step; the token handling above stays.

### 3.2 Authorisation

| Threat | Control | Evidence |
|---|---|---|
| **E** One bank reading another's data | Tenant bound from the token on every request; ORM filter fails closed; PostgreSQL row-level security with `FORCE`, app role is `NOBYPASSRLS` | `api/tenancy.py`, `migrations/0002`, `tests/test_tenancy.py`, `tests/test_postgres.py` |
| **E** Staff acting outside their role | Role checks per endpoint (only credit officers decide; only risk sees governance) | `api/auth.py: require_roles`, `tests/test_api_roles_consent.py` |
| **E** RM reading another branch's accounts | Branch scope on applications, alerts, simulator and portfolio views; RM with no branch sees nothing | `api/authz.py`, `tests/test_authz.py` |
| **E** MSME owner reading another factory | Factory check on every MSME route | `api/auth.py: ensure_factory_access` |
| **I** Cached view leaking across scopes | Cache key includes bank and branch scope | `api/routers/portfolio.py`, `tests/test_authz.py::test_portfolio_views_follow_branch_scope` |

Access matrix:

| | applications / alerts | decide | portfolio | governance, audit verify | MSME app |
|---|---|---|---|---|---|
| risk | whole bank | – | whole bank | ✓ | – |
| credit_officer | branch scope (default whole bank) | ✓ | branch scope | – | – |
| rm | branch scope only | – | branch scope | – | – |
| msme | own factory | – | – | – | own factory |

### 3.3 API edge

| Threat | Control | Evidence |
|---|---|---|
| **D** Request floods | Per-user, per-bank and per-address limits → 429 + `Retry-After`; WAF and autoscaling in prod | `tests/test_edge.py` |
| **T** Duplicate writes on retry | `Idempotency-Key` on every write; auth endpoints never replayed | `api/middleware.py`, `tests/test_auth.py::test_auth_endpoints_are_never_replayed_by_idempotency` |
| **I** Clickjacking, MIME sniffing, caching of credit data | CSP `default-src 'none'` and `frame-ancestors 'none'`, nosniff, `Cache-Control: no-store` on `/v1`, HSTS over HTTPS; SPA served with its own strict CSP | `api/security.py`, `web/nginx.conf`, `tests/test_ops.py` |
| **I** Error details leaking internals | RFC 9457 problem responses; unhandled errors return a generic 500 with a request id | `api/problems.py` |
| **I** Metrics exposure | `/metrics` not proxied by the web front; optional bearer token | `web/nginx.conf`, `tests/test_ops.py::test_metrics_token` |

### 3.4 Data at rest and in logs

| Threat | Control | Evidence |
|---|---|---|
| **I** Database dump, replica or backup read | Field-level Fernet encryption of personal data, free-text notes and consented snapshots; key rotation without downtime; Azure storage encryption (prod) | `api/crypto.py`, `tests/test_crypto.py` |
| **I** PII in logs | JSON logs mask phone, email, PAN, Aadhaar, bearer tokens and secret fields | `core/pii.py`, `tests/test_ops.py::test_json_logs_mask_pii_and_carry_request_id` |
| **I** PII in the audit trail | Inputs masked before storing; outputs stored as SHA-256 only | `api/audit.py` |
| **I** Data outside India | Start-up refuses non-India regions; Terraform restricts `location` to Indian regions | `core/settings.py: assert_data_residency`, `deploy/terraform` |
| **I** Data kept after consent ends | Revocation blocks pulls and deletes snapshots; expiry enforced before every pull | `agents/providers/consent.py`, `tests/test_api_roles_consent.py` |

### 3.5 Audit trail

| Threat | Control | Evidence |
|---|---|---|
| **T** Editing or deleting an audit entry | Per-bank SHA-256 hash chain written in the same transaction; PostgreSQL trigger refuses UPDATE/DELETE of chained rows | `api/audit_chain.py`, `migrations/0007`, `tests/test_audit_chain.py` |
| **T** Re-hashing the whole chain | Publish the head hash outside the database (prod: immutable Blob storage, daily signed report) | `POST /v1/audit/verify` returns `head_hash` |
| **R** Repudiating a decision | Decision, comment, user and time recorded and chained | `agents/orchestrator.py` |

### 3.6 AI components

| Threat | Control | Evidence |
|---|---|---|
| **T** LLM inventing numbers | Number guard rejects any number not in the facts; the template text is used instead | `agents/guard.py`, `tests/test_memo.py`, `tests/test_llm_resilience.py` |
| **E** Prompt injection steering a decision | The LLM only rewrites prose; scores, limits and decisions come from the model and policy engine; a human decides | `agents/memo_agent.py`, `agents/orchestrator.py` |
| **D** Slow or failing provider stalling credit work | Timeout, circuit breaker, per-bank concurrency cap, cache; every path falls back to the template | `agents/providers/llm.py`, `tests/test_llm_resilience.py` |
| **I** Personal data sent to the provider | Facts sent are aggregates and policy text; prod uses Azure OpenAI in an Indian region under the bank's tenant | `agents/*` facts dictionaries |

### 3.7 Background jobs and the queue

| Threat | Control | Evidence |
|---|---|---|
| **T** Lost or duplicated job | Transactional outbox; idempotent consumer with a conditional claim; dead-letter after retries | `api/jobs.py`, `worker/tasks.py`, `tests/test_jobs.py` |
| **E** A job crossing banks | The job row carries its bank; the worker binds that tenant before running | `worker/tasks.py: execute` |
| **I** Redis compromise | Redis holds no source of truth (cache entries, counters, queue messages carry job ids only); auth + TLS (prod: Azure Cache for Redis, private endpoint) | `api/kv.py` |

### 3.8 Supply chain and runtime

| Threat | Control | Evidence |
|---|---|---|
| **T** Vulnerable dependency | `pip-audit --strict` and `npm audit` block CI; hosted-LLM extras audited separately | `.github/workflows/ci.yml` |
| **T** Committed secret | gitleaks over the full history blocks CI | `.github/workflows/ci.yml` |
| **T** Insecure code patterns | bandit blocks CI; each suppression carries its reason | `.github/workflows/ci.yml` |
| **E** Container breakout impact | Non-root (uid 10001) images, read-only root filesystem and dropped capabilities in Kubernetes | `Dockerfile`, `deploy/k8s` |
| **T** Vulnerable OS packages in images | Trivy blocks fixable HIGH/CRITICAL findings | `.github/workflows/ci.yml` |

## 4. Open risks

| Risk | Why it is open | Plan |
|---|---|---|
| Demo defaults (JWT secret, field key, `demo123`) are public | One-command local demo | Production guard refuses them; prod reads Key Vault |
| Circuit breaker and LLM concurrency caps are per process | Simplicity | Move state to Redis if the LLM tier becomes shared |
| Audit chain head not yet anchored externally | Needs immutable storage | Daily job writing `head_hash` to Azure immutable Blob storage |
| No malware scan of uploaded documents | Document upload is stubbed | Defender for Storage on the upload container |
| Access tokens are not revocable before expiry | Stateless JWT | 15-minute lifetime keeps the window short; add a deny-list on `jti` if needed |
| Metrics token optional | Network policy is the primary control in Kubernetes | Required by policy in prod Helm values |
