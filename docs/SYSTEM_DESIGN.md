# System design decisions

How the prototype is built, what is design only, the capacity plan, and the architecture decision records
(ADRs) for the prototype round. Each one states the context, the decision,
what it costs, and how it is verified. Measured numbers are labelled as measured; the rest are design
assumptions.

## What is built and what is design only

✅ Done (running and tested) · 🟡 Partial · 🔭 Future (designed and documented, deliberately not built for the
prototype round: "don't overbuild").

| Layer | Prototype | Production path | Status |
|---|---|---|---|
| Web | React SPA; served by FastAPI in the free container, or by nginx in the full stack | Same build behind Azure Front Door / App Gateway WAF | ✅ / 🔭 |
| API | FastAPI, stateless, `/v1`, RFC 9457 errors, rate limits, idempotency | Horizontal pods behind a load balancer | ✅ |
| Jobs | Transactional outbox → Dramatiq workers on Redis (in-process in the lite profile); SSE progress | KEDA-scaled worker pods | ✅ / 🔭 |
| Storage | SQLite (lite demo); PostgreSQL 16 with migrations, a month-partitioned serving table and row-level security (full stack) | Azure Database for PostgreSQL Flexible Server, zone-redundant | ✅ / 🔭 |
| Cache | Redis (full stack), in-memory fallback | Azure Cache for Redis | ✅ / 🔭 |
| Lakehouse | DuckDB + Parquet medallion (bronze, silver, gold) | Databricks Delta, same layer contracts | ✅ / 🔭 |
| Models | LightGBM + SHAP, monotone constraints, isotonic calibration; IsolationForest + rules for EWS | MLflow registry, champion/challenger, scheduled retraining | ✅ / 🔭 |
| LLM | Deterministic template writer (default); Azure OpenAI / OpenAI adapters behind a resilient wrapper | Azure OpenAI in Central India | ✅ / 🟡 adapter untested live |
| Data sources | Mock Account Aggregator, synthetic GST, e-way bill, bank, power and EPFO feeds | Sahamati AA (bank as FIU), GSP, DISCOM feeds | 🟡 mock / 🔭 live |
| Observability | JSON logs, Prometheus metrics, OpenTelemetry traces, Grafana dashboard (compose profile) | Azure Monitor / managed Grafana | ✅ / 🔭 |
| Orchestration | Docker Compose | **Kubernetes (AKS) with HPA, KEDA and PDBs** (`deploy/k8s`): lint and schema validated, never deployed | 🔭 |
| Infrastructure as code | – | **Terraform for Central India** (`deploy/terraform`): `terraform validate` passes, never applied | 🔭 |
| Event streaming | Outbox relay to a Redis stream | Azure Event Hubs | 🔭 |
| Multi-region | – | Active/passive across Central and South India (both in India) | 🔭 |

## Capacity plan: 10 lakh accounts per bank

| Workload | Measured (prototype) | Extrapolation to 10 lakh accounts (**estimate**) |
|---|---|---|
| Nightly scoring + EWS batch | 915 accounts/s in one process, chunked and checkpointed (`ml/batch.py`, demo panel) | About 18 min in one process; about 5 min across 4 worker processes |
| Feature build (gold) | 18 lakh factory-months in 118 s on 10 processes (`data_gen/build.py`) | Incremental nightly: only the latest month per account, a few minutes on one 8-core worker |
| EWS rules over the full panel | 17.5 lakh account-months in 23 s (vectorised back-test) | Well under a minute per nightly run |
| Portfolio read | 18 ms (SQLite) / 22 ms (PostgreSQL), indexed and cached per bank and scope (ADR-003) | Pre-aggregated by month and band; account lists paginated by cursor |
| Synthetic data at scale | 50,000 × 36 panel in 2 min 12 s at 4.0 GB peak | The 1 lakh panel (`UP_DATASET=scale`) for benchmarks |
| Public demo container | Ready in 7 s; 325 MB after the full story (512 MB cap) | n/a |

The k6 load test of the API (p95 under concurrent users) is still to run, so API latency under load is 🟡.

## ADR-001 · Synchronous handlers, asynchronous where it matters

**Context.** The plan asked for async SQLAlchemy (`asyncpg`) across the API. The agent layer is synchronous and
CPU-bound: pandas, LightGBM, ReportLab and DuckDB. On the event loop, that work would block every other request.

**Decision.** Request handlers stay synchronous and run in FastAPI's thread pool with a pooled PostgreSQL
connection (psycopg 3). Heavy or slow work moves to background workers (ADR-005). Async is used only where a
request waits on I/O for a long time: the Server-Sent Events stream (ADR-007) and the health probes.

**Cost.** A thread per in-flight request. API pods scale horizontally (they are stateless), so concurrency comes
from more pods rather than from one event loop.

**Verified.** `tests/test_jobs.py` (SSE), `tests/test_api_contract.py` (probes).

## ADR-002 · Multi-tenancy at the session layer, Row-Level Security underneath

**Context.** One bank is one tenant. A missed `WHERE tenant_id = …` in any query would leak another bank's data.

**Decision.**
- Every business table carries `tenant_id`.
- The tenant comes from the signed JWT (`tid` claim) and is bound to the request session.
- A SQLAlchemy `do_orm_execute` hook adds the tenant filter to every select, update and delete, including
  primary-key lookups and bulk statements. New rows are stamped with the tenant, and a row for another tenant is
  refused.
- Request sessions fail closed: querying tenant data before the tenant is known raises.
- The only cross-tenant access is `allow_cross_tenant()`, used by login (the username decides the bank), the
  outbox relay and job dispatch. It is easy to grep for.
- On PostgreSQL, Row-Level Security policies (`FORCE ROW LEVEL SECURITY`, so they also bind the table owner)
  enforce the same rule for raw SQL. The application connects as a role that is neither a superuser nor
  `BYPASSRLS`.

**Cost.** One `set_config` per transaction on PostgreSQL.

**Verified.** `tests/test_tenancy.py` (two seeded banks: listing, by-id access, bulk updates, forged tokens,
fail-closed sessions) and `tests/test_postgres.py` (RLS on raw SQL, including writes).

## ADR-003 · PostgreSQL by default for the full stack, SQLite for the one-command demo

**Decision.**
- Docker Compose runs PostgreSQL 16 with Alembic migrations. `make demo` keeps SQLite, so the demo still needs
  nothing installed beyond Python and Node.
- Composite indexes back the hot queries: `applications(tenant_id, state)`, `applications(tenant_id, factory_id)`
  and `alerts(tenant_id, status, severity)`.
- Monthly account scores live in a serving table, `account_scores`, written by the monitoring batch only while
  consent allows new data. On PostgreSQL it is `RANGE`-partitioned by month. Old months can be detached without
  touching current data, and month filters prune to a single partition (checked with `EXPLAIN` in the tests).
  The portfolio screen reads this table with three set-based queries instead of scanning the lake per account.

**Measured** (laptop, 140 accounts, median of 15): `/portfolio` 109 ms → 18 ms on SQLite and 22 ms on
PostgreSQL, before caching.

**Verified.** `tests/test_postgres.py` checks that the migrations match the models, the partitioning and the
pruning. CI runs the whole suite against PostgreSQL.

## ADR-004 · Redis is an accelerator, never a single point of failure

**Decision.** Redis holds the portfolio response cache, rate-limit counters, idempotency records and the job
queue. Without `UP_REDIS_URL`, each of these falls back to an in-process implementation. If Redis fails at
runtime, cache and limits fail open (logged), and the API keeps serving.

- **Cache invalidation is event-driven.** Each tenant has a version counter. Any commit that touches
  applications, alerts, consents or scores bumps that counter, from a SQLAlchemy `after_commit` hook. A change to
  the clock bumps a global counter. Keys embed both versions, so a write makes stale entries unreachable at once,
  and the 30 s TTL only bounds memory.
- **Rate limits** use fixed one-minute windows: per user (600/min), per tenant (6,000/min) and per client IP on
  login (30/min). Over the limit, the API returns 429 problem+json with `Retry-After`.
- **Idempotency** is per user and key, stored for 24 h. The same key with the same body gets a replay
  (`Idempotency-Replayed: true`). The same key with a different body gets 422. A retry while the first request
  is still running gets 409. 5xx responses are not stored, so the client can retry them.

**Verified.** `tests/test_edge.py`, including an outage test against a Redis port nothing listens on.

## ADR-005 · Dramatiq for background jobs

**Context.** The plan offered ARQ or Dramatiq.

**Decision.** Dramatiq.
- Our job code is synchronous and CPU-bound. Dramatiq runs plain synchronous actors in worker threads; ARQ is
  asyncio-first and would need `run_in_executor` around everything.
- Retries with exponential backoff and jitter, time limits and a dead-letter queue are built in (`jobs.XQ` on
  Redis).
- The stub broker runs the same actors in-process, so the lite demo and the tests exercise the real code path
  without Redis.

**Consumer idempotency.** A job is claimed with a conditional `UPDATE … WHERE status IN ('queued','retrying')`.
A duplicate delivery finds nothing to claim and returns. A job whose worker died is reclaimed after a 15-minute
lease.

**Error handling.**
- Business-rule errors (no consent, wrong state) fail the job once, with no retry.
- Unexpected errors are retried, then dead-lettered.
- A job row that is not visible is retried, never acknowledged. This came out of an incident during
  development: stray workers from earlier runs, pointed at a deleted database, were silently skipping jobs.

**Verified.** `tests/test_jobs.py` covers retries with measured backoff, dead-lettering (stub and Redis),
duplicate delivery and business failures. A two-process smoke test (API plus `python -m worker` over Redis)
completes a 140-account batch in about 1.2 s.

## ADR-006 · Transactional outbox

**Decision.** Enqueuing a job and announcing a domain event (`alert.raised`, `application.decided`,
`application.disbursed`, `consent.revoked`) both write an `outbox` row in the same transaction as the change.
A relay publishes committed rows:
- job requests go to Dramatiq;
- domain events go to the Redis stream `udyampulse:events` (Azure Event Hubs in production).

A rolled-back change queues nothing. A crash after commit loses nothing, because the relay finds the row.
Delivery is at least once, and consumers are idempotent (ADR-005). Several relays can run side by side on
PostgreSQL (`FOR UPDATE SKIP LOCKED`).

**Verified.** `tests/test_jobs.py`: rollback queues nothing, failed publishes stay in the outbox until they
succeed, and domain events reach the stream.

## ADR-007 · Live progress over Server-Sent Events

**Decision.**
- Long work returns `202 Accepted` with a job id: the early-warning batch always, and scoring and memos when the
  client sends `Prefer: respond-async` (RFC 7240).
- `GET /v1/events?job=<id>` streams job updates and closes when the job finishes. The web client reads it with
  `fetch` so it can send the bearer token, and falls back to polling `GET /v1/jobs/<id>`.
- The stream polls the indexed `jobs` table every 400 ms with short-lived sessions, so no connection is held
  while a client listens. This works across any number of API and worker pods without a pub/sub dependency.
- **Production path:** Redis pub/sub or Web PubSub fan-out when connected clients reach the thousands.

**Verified.** `tests/test_jobs.py::test_async_scoring_returns_202_and_streams_progress`, and the Playwright demo
story, which scores, drafts the memo and plays six weeks through jobs.

## ADR-008 · API contract

**Decision.**
- Every business endpoint is under `/v1`.
- Every error is RFC 9457 problem+json, with a stable `code` and the `request_id`. Unhandled errors return a
  generic 500 and never leak internals.
- The request id is taken from `X-Request-ID`, or generated and validated, and is returned on every response.
- `/healthz` (liveness) checks no dependency. `/readyz` (readiness) checks the database, the model, the lake and
  Redis, and returns 503 to leave the load-balancer rotation.

**Verified.** `tests/test_api_contract.py`.

## ADR-009 · Observability: OpenTelemetry traces, Prometheus metrics, JSON logs

**Decision.**
- **Traces:** OTLP over HTTP, off unless `UP_OTEL_ENDPOINT` is set, so the demo needs no collector. Spans cover
  the request, each SQL statement and the background job. The job row stores the request's W3C `traceparent`,
  so one trace crosses the queue, and the API echoes `traceparent` so a user report leads straight to the trace.
- **Metrics:** RED metrics labelled by route template, never by raw path, job id, tenant or user. Queue depth
  and outbox backlog are read from PostgreSQL at scrape time, so every replica reports the same number and KEDA
  can scale workers on it. Two uvicorn processes in one container share counters through
  `PROMETHEUS_MULTIPROC_DIR`. That variable is set only in the API's start command, because prometheus_client
  switches mode whenever it exists, even when empty.
- **Logs:** one JSON object per line with the request id, trace id and tenant. Phone, email, PAN, Aadhaar,
  bearer tokens and secret fields are masked before the line is written.
- **Local stack:** `docker compose --profile observability up` adds Prometheus with six alert rules, Grafana
  with the service dashboard (`ops/grafana`) and Jaeger.

**Verified.** `tests/test_ops.py`, including a single trace from HTTP request to job. In the compose stack, one
async score produced a 27-span trace across `udyampulse-api` and `udyampulse-worker`. Both Prometheus
targets were up and the dashboard rendered under load (`docs/images/ops-grafana-overview.png`).

## ADR-010 · Sessions: short access tokens, rotating refresh cookies

**Decision.**
- Access tokens are JWTs that live 15 minutes, held in browser memory only.
- The refresh token is an opaque value in an httpOnly, SameSite=Strict cookie (Secure in production). Only its
  SHA-256 is stored, and it rotates on every use.
- A replayed refresh token revokes its whole family. There is a 15-second grace window for two tabs that share
  one cookie jar: the late tab is told to retry instead.
- Passwords use argon2id with RFC 9106 parameters. Legacy PBKDF2 hashes are upgraded at the next login.
- **Rejected:** long-lived access tokens in localStorage, which is the previous design (XSS exfiltration lasts
  8 hours).

**Verified.** `tests/test_auth.py`, and e2e tests for reload with the cookie, an ended session and sign-out
revocation.

## ADR-011 · Field-level encryption and a hash-chained audit trail

**Decision.**
- **Field encryption:** personal data, free-text notes and consented data snapshots are Fernet-encrypted in
  the ORM type layer. Keys are newest first in `UP_FIELD_KEYS`, and `python -m api.crypto rotate` re-encrypts
  in place.
- **Audit chain:** each bank's audit rows form a SHA-256 chain written inside the same transaction, ordered by
  a per-bank advisory lock on PostgreSQL. A PostgreSQL trigger refuses UPDATE and DELETE on chained rows.
  `POST /v1/audit/verify` recomputes the chain. Anchoring the head hash in immutable Blob storage is
  provisioned in Terraform; the daily anchoring job is the open item.

**Verified.** `tests/test_crypto.py` and `tests/test_audit_chain.py`, covering tampering on SQLite,
trigger refusal on PostgreSQL and concurrent writers.

## ADR-012 · Authorisation: roles plus branch scope

**Decision.** Role checks per endpoint, plus attribute checks on the account's cluster:
- Relationship managers see only the clusters they cover; an RM with no branch sees nothing.
- Risk always sees the whole bank.
- Portfolio caches are keyed by scope.

Bank isolation (ADR-002) sits underneath, so branch scope only ever narrows.

**Verified.** `tests/test_authz.py`.

## ADR-013 · Deployment: AKS with HPA, KEDA and PDBs; Terraform restricted to India

**Decision.**
- **Helm chart (`deploy/k8s`):**
  - A migration hook runs before rollout.
  - The API scales on CPU (HPA, 3 to 20 pods).
  - Workers scale on queued jobs (KEDA, 2 to 30 pods).
  - PodDisruptionBudgets keep capacity through node drains.
  - Pods run non-root with a read-only root filesystem, all capabilities dropped and seccomp RuntimeDefault,
    behind default-deny network policies.
- **Terraform (`deploy/terraform`):**
  - AKS with workload identity and the KEDA add-on.
  - Private PostgreSQL 16 with zone-redundant HA and geo-backup inside India.
  - Private Premium Redis, Key Vault and Storage, including a 7-year immutable `audit-anchors` container.
  - `location` validation rejects any non-Indian region at plan time.
- **Image:** the hosted-LLM SDK and MLflow moved out of the runtime image, and pip and the bundled test suites
  were stripped. The image went from 1.95 GB to 1.38 GB.

**Verified.**
- `helm lint`, `helm template` and `kubeconform -strict` against Kubernetes 1.30: 16 of 17 resources valid;
  the KEDA ScaledObject has no published schema and is skipped.
- `terraform validate` passes, and a plan with `location=eastus` is rejected.
- The API image ran with `--read-only --cap-drop ALL` and completed login, consent, scoring, memo, PDF and
  refresh. All of this runs in CI (`deploy`, `images`, `security` jobs).
- The Terraform has not been applied to a live subscription.
