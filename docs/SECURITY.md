# Security

Summary of the controls. The full STRIDE analysis, with evidence for every control, is in
`docs/THREAT_MODEL.md`. ✅ Done (built and tested) · 🟡 Partial · 🔭 Future.

## Controls

| Area | Control | Evidence | Status |
|---|---|---|---|
| Authentication | argon2id passwords (legacy hashes upgraded at login); 15-minute JWT kept in memory; rotating httpOnly SameSite=Strict refresh cookie, where reuse revokes the whole session family; constant-time failure for unknown users | `api/auth.py`, `tests/test_auth.py` | ✅ |
| Authorisation | Role checks on every endpoint; branch scope for relationship managers; only credit officers decide | `api/authz.py`, `tests/test_authz.py`, `tests/test_api_roles_consent.py` | ✅ |
| Tenant isolation | Bank bound from the token; ORM filter fails closed; PostgreSQL row-level security with a non-superuser role | `api/tenancy.py`, `tests/test_tenancy.py`, `tests/test_postgres.py` | ✅ (full stack) |
| Input validation | Typed request models (Pydantic), RFC 9457 errors, no internal details in 500s | `api/models/schemas.py`, `api/problems.py` | ✅ |
| Abuse limits | Per-user, per-bank and per-address limits (429 + `Retry-After`); idempotency keys on writes | `api/middleware.py`, `tests/test_edge.py` | ✅ |
| Transport and browser | CSP, `frame-ancestors`, nosniff, `Referrer-Policy`, `no-store` on API data, HSTS over HTTPS | `api/security.py`, `web/nginx.conf`, `tests/test_ops.py` | ✅ |
| Encryption in transit | TLS at the host (Hugging Face Spaces, Caddy profile, App Gateway in the production design) | `Caddyfile`, `deploy/huggingface` | ✅ host-provided |
| Encryption at rest | Field-level Fernet encryption of personal data, notes and consented snapshots, with key rotation | `api/crypto.py`, `tests/test_crypto.py` | ✅ |
| Audit integrity | Per-bank SHA-256 hash chain; a PostgreSQL trigger blocks edits and deletes; "Verify chain" in Governance | `api/audit_chain.py`, `tests/test_audit_chain.py` | ✅ (external anchoring 🔭) |
| Secrets | None needed for the demo. Production refuses demo secrets (`UP_ENV=production`). gitleaks scans the whole history in CI | `core/settings.py`, `.github/workflows/ci.yml` | ✅ |
| Supply chain | Blocking pip-audit, npm audit, bandit and Trivy image scans; pinned versions | `.github/workflows/ci.yml` | ✅ |
| Logging | JSON logs with request and trace ids; PII and secrets masked | `core/logs.py`, `core/pii.py` | ✅ |
| Runtime | Non-root containers; the image runs with a read-only root filesystem and all capabilities dropped | `Dockerfile`, `deploy/huggingface/Dockerfile` | ✅ |
| Data residency | Start-up refuses a non-India region; Terraform rejects non-India locations | `core/settings.py`, `deploy/terraform/variables.tf` | ✅ (Terraform is a design artefact 🔭) |

## Public demo hardening

The live demo is a prototype on synthetic data:
- **Accounts:** published demo personas only, password `demo123`.
- **Data:** synthetic only. Nothing is persisted, and the database is reseeded on every start.
- **Visible notice:** a "Prototype · synthetic data · not a lending decision" banner on every screen.
- **No indexing:** `noindex` meta tag and `X-Robots-Tag` header, plus a `robots.txt` that disallows everything.
- **Abuse limits:** rate limits are active.
- **No external calls:** no API keys and no outbound LLM calls, because the template writer is used.

## Reporting

This is a student prototype. Please report issues privately to the team (contact in the README) rather than
opening a public issue.
