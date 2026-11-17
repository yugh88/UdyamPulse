# Upgrade audit (P0)

Audit of the prototype at commit `30999a0`, written before any code change for the prototype round.
Everything marked **measured** was run on this machine on 16 Nov 2026 (Apple M3 Pro, 11 cores, 18 GB RAM,
Python 3.11, Node 20.19). Everything else comes from reading the code.

## 1. Baseline: what was run

| Check | Result |
|---|---|
| `make setup` | Passes in 41 s |
| `make pipeline` (generate, lake, train, back-test, seed) | Passes in 100 s wall-clock on a cold run (25 s CPU). The README says "about 20 seconds". |
| `make test` | 29 passed in 13 s |
| `ruff check .` | Clean |
| `npm run build` | Passes. One JS bundle: 725 KB, 210 KB gzipped. |
| Reports reproducible | Yes. Re-running changed only the timestamp and MLflow run id in `ml/MODEL_CARD.md`. |
| Docker Compose | **Not verified.** The Docker daemon was not running. |

Size: about 7,500 lines. Backend 3,900 lines of Python, frontend 1,300 lines of TypeScript, 29 tests, no frontend tests.

Endpoint latency, in-process through the FastAPI test client, 140 monitored accounts (**measured**, median of 5):

| Endpoint | Median | Note |
|---|---|---|
| `GET /portfolio` | 109 ms | 48 KB response, no pagination |
| `POST /sim/advance?days=42` | 365 ms | Runs the whole EWS batch inside the request and writes 148 audit rows |
| `GET /alerts`, `/applications`, `/applications/{id}`, `/model`, `/sim/clock` | 2–3 ms | |

## 2. What works and should be kept

- **The end-to-end story runs.** Apply, consent, score, memo, decision, disburse, monitor, alert, revoke. The state machine in `agents/orchestrator.py` rejects invalid transitions.
- **Provider interfaces are clean.** `agents/providers/*` hides the LLM, search, consent, document parser and lake behind protocols, each with a local default. No cloud key is needed.
- **The LLM cannot invent numbers.** `agents/guard.py` rejects any generated number that is not in the structured facts, and the template writer is the default.
- **Scoring is explainable and exact.** SHAP contributions convert to score points and sum to the score (covered by a test).
- **The time-based split is real.** Train months 4–12, validation 13–15, gap month 16, test 17–24.
- **Consent is enforced on every pull**, with an append-only ledger and a deletion job on revoke.
- **Every agent tool call is audited** with masked inputs and a SHA-256 of the output.
- **The India data-residency check** runs at start-up.

## 3. What is weak

### 3.1 UX and frontend

| # | Finding | Where |
|---|---|---|
| U1 | Saturated palette (navy `#0B1033`, magenta `#E5397A`, violet `#7B5CFF`), pure white cards, no dark mode. | `web/src/index.css` |
| U2 | Inter is loaded from the Google Fonts CDN, so the demo is not offline-safe. | `web/index.html` |
| U3 | No loading states. Pages render blank until data arrives (`if (!app) return <ErrorNote …>`). Only four ad-hoc empty states. No retry on error. | all pages |
| U4 | An expired or invalid token is never handled. A 401 leaves the user on a broken page until they sign out by hand. | `web/src/lib/api.ts` |
| U5 | State is conveyed by colour alone in places: pillar swatches, positive/negative bars, band chips without icons. | `Reasons.tsx`, `ui.tsx` |
| U6 | No shell features: no sidebar, breadcrumbs, ⌘K search, keyboard shortcuts or role switcher. Feedback is a single inline toast on the cockpit. | `Layout.tsx` |
| U7 | Hindi covers only the plan summary paragraph. All other MSME strings are English. No i18n library. | `MsmeApp.tsx` |
| U8 | The service worker caches only `/` and the icon. The hashed JS and CSS are not cached, so the "offline shell" does not load offline. | `web/public/sw.js` |
| U9 | No code splitting. Recharts ships in the initial bundle on every route, including login. | `App.tsx` |
| U10 | Types are loose: 23 uses of `any` in pages. No ESLint, no Prettier, no component tests, no E2E tests. | `web/` |
| U11 | Screens the plan asks for do not exist: what-if simulator, score migration matrix, alert drawer with bulk actions, guided demo mode, `/system` page, compliance checklist, AI usage log, consent ledger view for Risk. | — |
| U12 | The signal chart shows three series only. Receivables and compliance signals are not exposed by the API. | `SignalChart.tsx`, `applications.py` |
| U13 | Indian number formatting is partial: lakh and crore helpers exist, but there is no `₹12,34,567` grouping helper used consistently. | `web/src/lib/format.ts` |

### 3.2 Backend correctness and code quality

| # | Finding | Where |
|---|---|---|
| B1 | **Audit writes break transaction atomicity.** `log_event` commits by default, and `Agent.tool` calls it mid-operation. A scoring request commits several times, so a failure half-way leaves partial state and audit rows for work that was rolled back. | `api/audit.py`, `agents/base.py` |
| B2 | **GET requests write data.** `GET /msme/{id}/readiness` performs a consented data pull on every view, adding a `DataSnapshot`, a ledger `DATA_PULL` row and three audit rows. `consent.active()` also writes `EXPIRED` from read paths. | `api/routers/msme.py`, `agents/providers/consent.py` |
| B3 | The audit log is not tamper-evident. Rows carry an output hash but no chain to the previous row. | `api/models/db.py` |
| B4 | A global `ValueError` handler turns any `ValueError` anywhere into a 422, which hides real bugs as client errors. | `api/main.py` |
| B5 | Error bodies are inconsistent: `{"detail"}`, `{"detail","code"}`, and FastAPI's validation list. | `api/main.py` |
| B6 | No API versioning, no pagination (`/alerts`, `/applications` and `/portfolio` return everything), no idempotency. A double-clicked "Approve" is caught only by the state machine; a double-clicked "create application" creates two. | `api/routers/*` |
| B7 | Any RM or credit officer can act on any alert or application. There is no branch or tenant check. | `api/routers/portfolio.py` |
| B8 | Memo PDFs are written to local disk (`var/memos`), which breaks as soon as there is more than one API pod. | `agents/memo_agent.py` |
| B9 | The LLM call uses `asyncio.run` inside a sync handler with no timeout, no circuit breaker and no cache. With a real provider configured, a slow API would hang the demo. | `agents/providers/llm.py` |

### 3.3 Scale bottlenecks

| # | Finding | Where |
|---|---|---|
| S1 | **The whole lake is loaded into pandas in each API process**, and every lookup is a full-frame boolean filter. `/portfolio` filters the scores frame once per account, so cost grows with accounts × rows. It takes 109 ms at 140 accounts and cannot serve 10 lakh. | `agents/providers/lake.py`, `portfolio.py` |
| S2 | `/portfolio` runs one consent query per account (N+1). | `portfolio.py` |
| S3 | **The EWS batch runs synchronously inside an HTTP request**, one account at a time, with a commit and at least two audit rows per account. There are no workers, no queue and no checkpoint. | `agents/ews_agent.py` |
| S4 | SQLite only, with `create_all` and no migrations. The only indexes are on `factory_id` and `application_id`. Nothing indexes `state`, alert `status` or `severity`. | `api/models/db.py` |
| S5 | No multi-tenancy. No table has a `tenant_id`. | `api/models/db.py` |
| S6 | No cache, no rate limiting, no Redis. Every authenticated request also reads the user row from the database. | `api/auth.py` |
| S7 | The data generator simulates each factory in a Python loop. It has not been run above 500 factories, so its speed at 1 lakh is unknown. | `data_gen/generate.py` |
| S8 | The API image trains the model at container start, so each new pod takes over a minute to become healthy and pods can disagree on the model. | `Dockerfile` |

### 3.4 Security and operations

| # | Finding | Where |
|---|---|---|
| X1 | The JWT secret has a hard-coded default and nothing stops a production start with it. Tokens live for 8 hours with no refresh, and sit in `localStorage`. | `core/settings.py`, `web/src/lib/auth.tsx` |
| X2 | Passwords use PBKDF2-SHA256 at 120,000 iterations. The plan asks for argon2. | `api/auth.py` |
| X3 | No security headers (CSP, HSTS, `X-Content-Type-Options`, `frame-ancestors`). CORS allows all methods and headers. | `api/main.py` |
| X4 | PII columns are stored in plain text. Masking applies to audit inputs only. | `api/models/db.py` |
| X5 | Logs are unstructured. There are no request ids, metrics or traces. `/health` does not check the database. | `api/main.py` |
| X6 | Both images run as root. The web image serves the Vite dev server. Compose loads `.env.example`, including the default secret. | `Dockerfile`, `web/Dockerfile`, `docker-compose.yml` |
| X7 | CI security scans cannot fail the build (`pip-audit … \|\| echo`). There is no bandit, gitleaks, ESLint, frontend test, contrast check or Docker build. | `.github/workflows/ci.yml` |
| X8 | No threat model, capacity plan, performance report, Kubernetes manifests or Terraform. | `docs/` |

### 3.5 ML and decision quality

These are stated plainly because the plan asks for honest numbers.

| # | Finding | Evidence |
|---|---|---|
| M1 | **Large gap between train and test.** AUC is 0.995 on train, 0.916 on validation and 0.811 on the out-of-time test. | `ml/reports/metrics.json` |
| M2 | **The test set is small in events.** 121 positives in 3,855 rows, and rows are repeated months of the same factories, so the effective sample is smaller than the row count. No confidence interval is reported. | `metrics.json` |
| M3 | Probabilities are not calibrated and no calibration curve exists. Test Brier is 0.0256 against about 0.030 for always predicting the base rate, which is a modest gain. | `metrics.json` |
| M4 | **EWS precision is 0.28** (61 alerted accounts, 17 reached SMA-2 within 6 months). Recall is 22 of 22, but 22 events is too few to claim 100% in general. | `ml/reports/ews_backtest.md` |
| M5 | Discrimination is uneven across sectors: AUC 0.71 for auto components against 0.91 for ceramics. The fairness report has ratios but no pass/fail threshold. | `ml/reports/fairness.json` |
| M6 | Drift is PSI of train against test for ten features, computed once. There is no monthly series and no warning badge. | `ml/reports/drift.json` |
| M7 | No challenger model and no what-if endpoint. | `ml/` |
| M8 | **The hero factory is scripted.** `_apply_hero_script` pins its stress months so the demo shows exactly e-way −42% and kWh −32%. This is fine for a demo but must be disclosed, and the hero must stay out of any headline metric claim. | `data_gen/generate.py` |
| M10 | **The model is not monotonic in signals that have a clear economic direction.** Found while building the what-if simulator: for some factories a 30% fall in dispatches, or a 15-point rise in top-buyer share, *raises* the score by 8 to 25 points. For the hero, a 26% fall in the 3-month e-way bill count adds 21 points on its own. This is the overfitting in M1 showing up in individual decisions. Fix in P5a: monotone constraints on directional features, then report the effect on AUC. Until then the simulator shows what the model really does, labelled as a simulation. **Resolved 18 Nov 2026:** monotone constraints on 61 of 67 features (`ml/features.py: MONOTONE`, method `intermediate`; `advanced` and `extra_trees` with `advanced` left violations), plus open purchase orders treated as a stock in the simulator. Demo test AUC 0.810 → 0.831, train AUC 0.995 → 0.967. Over 200 factories, wrong-way moves for a 30% dispatch fall went from 120 (mean 21 points) to 6 (mean 3); bounces, bank inflows and days-to-pay never move the wrong way. Bounded remaining exceptions come from unconstrained intensity features (`tests/test_monotone.py`). Hero score 723 → 742, still Approve. | `ml/simulate.py`, measured 16 Nov 2026 |
| M9 | A unit test asserts the AUC target is met, which ties the test suite to a metric and creates pressure to tune toward it. | `tests/test_scoring.py` |

## 4. Ranked fix list

Ranked by demo risk first, then judge impact, then effort. Phase refers to section 7 of the plan.

| Rank | Fix | Findings | Phase |
|---|---|---|---|
| 1 | Self-host Inter, add loading, empty and error states everywhere, and handle 401 by returning to login | U2, U3, U4 | P1 |
| 2 | New design tokens for light and dark, contrast check in CI, icon + label + colour for every state | U1, U5 | P1 |
| 3 | UI component library and new shell: sidebar, top bar, ⌘K, theme toggle, toasts, breadcrumbs | U6 | P1 |
| 4 | Make audit writes join the caller's transaction, and stop GET requests from writing | B1, B2 | P3 (first) |
| 5 | Rebuild the six screens on the new components, with code-split routes and typed API responses | U9, U10, U12, U13 | P2 |
| 6 | Missing screens: what-if simulator, migration matrix, alert drawer, MSME Hindi through i18n | U7, U11, M7 | P2 |
| 7 | `/v1`, problem+json errors, cursor pagination, idempotency keys, request ids, `/healthz` and `/readyz` | B4, B5, B6, X5 | P3 |
| 8 | PostgreSQL with Alembic and indexes, `tenant_id` on every table, row-level security, two seeded banks and an isolation test | S4, S5, B7 | P3 |
| 9 | Move EWS, scoring and memo generation to workers with an outbox, retries, a dead-letter queue and SSE progress | S3, B9 | P3 |
| 10 | Replace per-request pandas scans with indexed lookups and a cached portfolio aggregate; add Redis cache and rate limiting | S1, S2, S6 | P3 |
| 11 | Hash-chained audit with a verify endpoint, field-level PII encryption, argon2, short JWT with refresh cookie, security headers | B3, X1, X2, X3, X4 | P4 |
| 12 | Structured logs, Prometheus metrics, traces, Grafana dashboard; non-root multi-stage images; model trained at build time, not at start | X5, X6, S8, B8 | P4 |
| 13 | Blocking CI scans, ESLint, Vitest, Playwright with axe, Lighthouse budget | X7, U10 | P1–P6 |
| 14 | Calibration, monotone constraints, EWS operating-point table, challenger, monthly PSI, fairness thresholds, bootstrap confidence intervals | M1–M7, M9, M10 | P5a, P5 |
| 15 | Vectorised generator to 1 lakh factories, batch benchmarks, k6 load test, capacity plan and performance report | S7, X8 | P5 |
| 16 | Guided demo mode, reset in under 3 s, `/system` page, service worker that caches the built assets, README and media | U8, U11 | P6 |
| 17 | Threat model, Kubernetes manifests with HPA and KEDA, Terraform skeleton | X8 | P4 |

## 5. Risks and decisions needed before P3

1. **Async SQLAlchemy across the whole API.** The agent layer is synchronous and CPU-bound (pandas, LightGBM, ReportLab). Converting every handler to `asyncpg` would touch every file and every test for little gain, because the heavy work must run off the event loop anyway. Recommended: keep the request handlers synchronous in FastAPI's thread pool, move heavy work to workers, and use async only where it matters (SSE, health, the outbox relay). This deviates from section 3.2 item 1 of the plan and needs a yes or no.
2. **Docker is not running on this machine, and k6 is not installed.** The Compose stack, the observability profile and the load test cannot be verified until Docker Desktop is started and `brew install k6` is run. PostgreSQL and Redis binaries are present through Homebrew, so P3 can be developed and tested against them directly.
3. **ML numbers may not improve.** Calibration and a better EWS operating point are likely to help Brier score and precision. AUC may stay near 0.81, and precision gains will cost recall or lead time. Whatever the re-run gives is what gets reported.
4. **Scope.** The plan is about ten working days of work. Kubernetes manifests and Terraform will be written and linted but not applied, as the plan allows.
