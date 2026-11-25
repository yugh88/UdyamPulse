# Team and ownership

**Team Legit · VIT Bhopal University** · Visionet Techthon 2026, Round 2

| Member | Registration | Programme | Role |
|---|---|---|---|
| **Yugh Juneja** (team representative) | 23BCE11163 | B.Tech CSE | Tech Lead & Solution Architect |
| **Kinjal Gupta** | 23MIP10052 | Integrated M.Tech CSE (AI) | Product, UX & Validation Lead |
| **Aditya Raj** | 23BCE10772 | B.Tech CSE | Database, Data Validation & QA Lead |

"Everyone owns a piece. Everyone knows the whole."
- Each member commits their own work from their own machine and git identity, and explains it at evaluation.
- The remaining work is split about a third each (`docs/TASKS.md`).

**Commit history, stated plainly.** Up to 18 Nov 2026 every commit in this repository was made under Yugh's
identity. From 18 Nov, Kinjal and Aditya own their areas and commit their own changes. The "What I built"
sections below list only what each person's own commits show; they are updated as those commits land.

## Ownership

| Member | Owns, and will explain at evaluation |
|---|---|
| **Yugh Juneja** (project lead) | End-to-end architecture and system design; the agent layer (orchestrator = planner, data agent = tool agent, credit-memo agent, guard = review agent) and how components communicate; the API, loan state machine, consent ledger, hash-chained audit and change tracking; the synthetic data generator, features, LightGBM + SHAP scoring, calibration, EWS rules and real-data benchmarks (SBA, Polish); the web app and the cream redesign; security and threat model; scalability (capacity plan, Redis / workers, benchmarks, `/system` page); free deployment and CI/CD; driving the live demo; anchoring Q&A on architecture, model, scale, security and compliance |
| **Kinjal Gupta** | Problem framing, personas and user journeys; design review of every screen against the mockups; natural Hindi for the MSME app; plain-English wording on every screen; accessibility checks (Lighthouse, keyboard, 200% zoom); real user validation sessions; innovation and impact narrative; deck design and the backup demo video; anchoring Q&A on users, UX, Hindi, validation, innovation and impact |
| **Aditya Raj** | The database: PostgreSQL schema and migrations for applications, alerts, consent and audit tables, the month-partitioned serving table and the demo seed data; data validation (leakage checks, data-quality checks); end-to-end testing; verifying every reported metric against its source report; the model card and the leakage write-up; the risk review; anchoring Q&A on data, database, validation, testing and limitations |

---

## Yugh Juneja: Tech Lead & Solution Architect

**What I built** (from my commits, Round 2 branch):
- **Architecture audit and system design:** `docs/UPGRADE_AUDIT.md`, `docs/SYSTEM_DESIGN.md` (ADR-001 to 013).
- **Multi-tenancy:** bank isolation with PostgreSQL row-level security (`api/tenancy.py`, `migrations/`).
- **Background work:** Redis caching, rate limits and idempotency (`api/kv.py`, `api/cache.py`,
  `api/middleware.py`); background jobs through a transactional outbox with SSE progress (`api/jobs.py`,
  `worker/`).
- **Security:** argon2id and rotating refresh sessions (`api/auth.py`); field encryption (`api/crypto.py`);
  the hash-chained audit (`api/audit_chain.py`); branch-scoped access (`api/authz.py`); LLM resilience
  (`agents/providers/llm.py`).
- **Observability:** OpenTelemetry and Prometheus.
- **Deployment and CI:** the single-container image, the Render blueprint, Helm and Terraform designs, CI with
  security gates.
- **Data and models:** the synthetic data generator, features, LightGBM scoring with SHAP reasons and monotone
  constraints, calibration, EWS rules and the real-data benchmarks (`data_gen/`, `data_real/`, `ml/`).
- **Web app:** every screen, and the cream redesign with change tracking (what changed, from what, to what)
  backed by `api/changes.py`.

**Why it's built this way.**
- The bank decides; agents only recommend, through a deterministic state machine.
- Every action is audited on a tamper-evident chain.
- The demo runs free with no keys.
- The production path (PostgreSQL, Redis, workers, AKS) is designed and measured, not overbuilt.

**Key files:** `api/`, `agents/`, `worker/`, `data_gen/`, `ml/`, `web/src/`, `deploy/`, `.github/workflows/ci.yml`,
`docs/SYSTEM_DESIGN.md`, `docs/THREAT_MODEL.md`

**Three questions I can answer.**
1. *How does it scale to 10 lakh accounts?*
   - Stateless API pods, queue + workers, a month-partitioned serving table and a chunked, resumable nightly
     batch.
   - Measured 8,752 accounts/s in one process on 50,000 factories, so about 2 minutes for 10 lakh (*estimate*).
2. *What if the LLM fails?* A timeout, circuit breaker and per-bank cap all fall back to a deterministic
   template. Numbers never come from the LLM, and a guard rejects any that do.
3. *How is one bank's data kept from another's?* The bank is bound from the token on every request, the ORM
   filter fails closed, and PostgreSQL row-level security sits underneath, tested both ways.

## Kinjal Gupta: Product, UX & Validation Lead

**My work** (each task is a GitHub issue assigned to me, #2–#10, and a pull request from my own account):
- **UI redesign pull request (K10):** reviewing each redesigned screen against the mockups and opening the PR
  that brings it into `main`.
- **Design review (K1):** every screen compared with its mockup; each difference raised as a `design` issue.
- **Hindi (K2):** the MSME app rewritten in simple, everyday Hindi that a factory owner would use.
- **Plain English (K3):** labels, buttons, empty states and reasons a busy bank officer understands in one read.
- **Accessibility (K4):** Lighthouse scores, keyboard-only walkthrough and 200% zoom on the key screens.
- **Real user validation (K5):** sessions with a banker, an MSME owner and the Visionet specialist, recorded in
  `docs/VALIDATION.md` (role only, never invented).
- **Deck and demo video (K6, K7):** the final deck design and the 2-minute backup video.

**Why it's built this way** (the experience she owns):
- Calm, readable screens for bank staff: one job per screen, every change visible at a glance.
- Plain language and Hindi for MSME owners.
- Accessibility checked automatically: WCAG 2.2 AA contrast in CI and axe in every browser test.

**Key files:** `web/src/i18n/` (`hi.ts`, `en.ts`), `docs/USERS.md`, `docs/VALIDATION.md`,
`docs/PRESENTATION_OUTLINE.md`, `deck/`

**Three questions I can answer.**
1. *How do low-literacy owners use it?* Hindi, icons beside every status, plain-language reasons, a 90-day plan
   as a checklist, and WhatsApp-style updates (mock).
2. *Is it accessible?* Contrast is checked in CI and axe runs on every key screen in both themes. Status never
   relies on colour alone.
3. *What did real users tell you?* From `docs/VALIDATION.md`: only the sessions actually held.

## Aditya Raj: Database, Data Validation & QA Lead

**What I own:**
- **Database:** the PostgreSQL schema and migrations (`migrations/versions/`) for applications, alerts,
  consent, audit and change-tracking tables; the `account_scores` serving table, RANGE-partitioned by month;
  the demo seed data (`api/seed.py`).
- **Data validation:** leakage checks (data up to the scoring month only; shuffled-label runs) and the data
  quality and reconciliation checks run on every data pull.
- **End-to-end testing:** the browser journey tests and the API suite on SQLite and PostgreSQL in CI.
- **Metrics verification:** every number in the README and the deck traced to its report file, labelled
  measured or estimated, synthetic or real.
- **Model card and leakage write-up:** `ml/MODEL_CARD.md` and the SBA leakage story.
- **Risk review:** `docs/LIMITATIONS_AND_RISKS.md`.

**Why it's built this way** (the data discipline he owns):
- One schema, versioned migrations, tested on both SQLite (demo) and PostgreSQL (production path) on every change.
- Bank data isolated by row-level security; the serving table partitioned by month so it scales to 10 lakh accounts.
- Real and synthetic results never blended; every leak found is reported, not hidden.

**Key files:** `migrations/`, `api/models/db.py`, `api/seed.py`, `tests/`, `web/e2e/`, `ml/MODEL_CARD.md`,
`ml/reports/`, `docs/LIMITATIONS_AND_RISKS.md`

**Three questions I can answer.**
1. *How is the database designed?*
   - Applications, alerts, consents and the consent ledger, a hash-chained audit log, and change events, all
     scoped by bank with row-level security.
   - `account_scores` is partitioned by month, so the nightly batch and the queries touch only the months they need.
   - Migrations run in CI against PostgreSQL with a non-superuser role, so RLS is really enforced.
2. *How do you avoid leakage?*
   - Features use data up to the scoring month only, checked by an automated audit.
   - 8 shuffled-label runs scatter around 0.5.
   - Splits are by time and by factory.
   - We found and removed the SBA loan-term leak (0.914 → 0.687, both stored in the report).
3. *How do you know the numbers are right?* Each one is traced to the report that produced it and labelled
   measured or estimated, synthetic or real: product model AUC 0.848 (0.842–0.854) on synthetic data; SBA 0.687
   (0.658–0.713) and Polish 0.954 on real data.
