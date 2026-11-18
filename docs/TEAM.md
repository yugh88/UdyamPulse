# Team and ownership

**Team Legit · VIT Bhopal University** · Visionet Techthon 2026, Round 2

| Member | Registration | Programme | Role |
|---|---|---|---|
| **Yugh Juneja** (team representative) | 23BCE11163 | B.Tech CSE | Tech Lead & Solution Architect |
| **Kinjal Gupta** | 23MIP10052 | Integrated M.Tech CSE (AI) | Product, UX & Validation Lead |
| **Aditya Raj** | 23BCE10772 | B.Tech CSE | Data & ML Lead |

"Everyone owns a piece. Everyone knows the whole."
- Each member commits their own work from their own machine and git identity, and explains it at evaluation.
- The remaining work is split about a third each (`docs/TASKS.md`).

**Commit history, stated plainly.** Up to 18 Nov 2026 every commit in this repository was made under Yugh's
identity. From 18 Nov, Kinjal and Aditya own their areas and commit their own changes. The "What I built"
sections below list only what each person's own commits show; they are updated as those commits land.

## Ownership

| Member | Owns, and will explain at evaluation |
|---|---|
| **Yugh Juneja** | End-to-end architecture and system design; the agent layer (orchestrator = planner, data agent = tool agent, credit-memo agent, guard = review agent) and how components communicate; the API, loan state machine, consent ledger and hash-chained audit; integration of scoring and EWS into the product; security and threat model; scalability (capacity plan, PostgreSQL / Redis / workers, benchmarks, `/system` page); free deployment and CI/CD; driving the live demo; anchoring Q&A on architecture, scale, security and compliance |
| **Kinjal Gupta** | Problem framing, personas and user journeys; the design system and all screens; MSME PWA and Hindi; accessibility (WCAG AA); guided-demo copy; real user validation sessions; innovation and impact narrative; deck design and the demo video; anchoring Q&A on users, UX, innovation and impact |
| **Aditya Raj** | Synthetic data generator and calibration; features; LightGBM + SHAP; calibration; EWS rules and alert ranker; metrics with CIs; the leakage findings; real public benchmarks (SBA, Polish); fairness and drift; model card; anchoring Q&A on data, model, validation and limitations |

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

Commits to date also cover the data, ML and UI work that Kinjal and Aditya now own.

**Why it's built this way.**
- The bank decides; agents only recommend, through a deterministic state machine.
- Every action is audited on a tamper-evident chain.
- The demo runs free with no keys.
- The production path (PostgreSQL, Redis, workers, AKS) is designed and measured, not overbuilt.

**Key files:** `api/`, `agents/`, `worker/`, `migrations/`, `deploy/`, `.github/workflows/ci.yml`,
`docs/SYSTEM_DESIGN.md`, `docs/THREAT_MODEL.md`

**Three questions I can answer.**
1. *How does it scale to 10 lakh accounts?*
   - Stateless API pods, queue + workers, a month-partitioned serving table and a chunked, resumable nightly
     batch.
   - Measured 915 accounts/s per process, so about 5 minutes on four processes (*estimate*).
2. *What if the LLM fails?* A timeout, circuit breaker and per-bank cap all fall back to a deterministic
   template. Numbers never come from the LLM, and a guard rejects any that do.
3. *How is one bank's data kept from another's?* The bank is bound from the token on every request, the ORM
   filter fails closed, and PostgreSQL row-level security sits underneath, tested both ways.

## Kinjal Gupta: Product, UX & Validation Lead

**What I built:** _to be filled from Kinjal's own commits from 18 Nov (UI polish, Hindi review, accessibility,
validation sessions, guided-demo copy, deck, video)._

**Why it's built this way** (the design she owns):
- Calm, dense, explainable screens for bank staff.
- Plain language and Hindi for MSME owners.
- Accessibility checked automatically: WCAG 2.2 AA contrast in CI and axe in every browser test.

**Key files:** `web/src/` (pages, features, components, `styles/tokens.css`, `i18n/`), `docs/USERS.md`,
`docs/VALIDATION.md`, `docs/PRESENTATION_OUTLINE.md`

**Three questions I can answer.**
1. *How do low-literacy owners use it?* Hindi, icons beside every status, plain-language reasons, a 90-day plan
   as a checklist, and WhatsApp-style updates (mock).
2. *Is it accessible?* Contrast is checked in CI and axe runs on every key screen in both themes. Status never
   relies on colour alone.
3. *What did real users tell you?* From `docs/VALIDATION.md`: only the sessions actually held.

## Aditya Raj: Data & ML Lead

**What I built:** _to be filled from Aditya's own commits from 18 Nov (EWS ranker, approval-uplift chart,
expected loss and pricing, SBA approval-time features, leakage visual, metrics source of truth)._

**Why it's built this way** (the method he owns):
- Gradient-boosted trees with TreeSHAP for tabular credit data, with monotone constraints.
- Time + factory-group evaluation with bootstrap CIs.
- Real and synthetic results never blended.
- Every leak found is reported, not hidden.

**Key files:** `data_gen/`, `data_real/`, `ml/`, `ml/MODEL_CARD.md`, `docs/DATA_STRATEGY.md`,
`docs/DATA_SOURCES.md`

**Three questions I can answer.**
1. *Is the data real?*
   - The product model is synthetic, calibrated to MoSPI IIP: AUC 0.848 (0.842–0.854).
   - The method is validated on real data: SBA 0.687 (0.658–0.713) and Polish 0.958.
2. *How do you avoid leakage?*
   - Features use data up to the scoring month only, checked by an automated audit.
   - 8 shuffled-label runs scatter around 0.5.
   - Splits are by time and by factory.
   - We found and removed the SBA loan-term leak (0.915 → 0.687).
3. *How noisy are the alerts?* At the chosen operating point (synthetic): recall 0.866, median lead 90 days,
   precision 0.314.
