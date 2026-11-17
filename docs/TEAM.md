# Team and ownership

**Team Legit · VIT Bhopal University** · Visionet Techthon 2026, Round 2

> **PROPOSED, team to confirm.** The split below is a suggestion organised by area. Replace the placeholders
> with real names, and keep each person's claims to what they actually built and can explain. Nothing here
> asserts who wrote what.

| Member | Branch | Proposed ownership area | Key files | Will explain at evaluation |
|---|---|---|---|---|
| _Name (to add)_ | _Branch_ | Data & ML | `data_gen/`, `data_real/`, `ml/` | Synthetic panel and calibration, features, LightGBM + SHAP, monotone constraints, EWS, metrics and CIs, real benchmarks |
| _Name (to add)_ | _Branch_ | Backend & agents | `api/`, `agents/`, `worker/`, `migrations/` | API contract, state machine, agents and guard, consent, audit chain, tenancy, jobs |
| _Name (to add)_ | _Branch_ | Frontend & UX | `web/src/` | Design system, screens, accessibility, Hindi, guided demo |
| _Name (to add)_ | _Branch_ | Deployment & docs | `deploy/`, `.github/`, `docs/`, `README.md` | Free deployment, CI/CD, security gates, README and deck |

---

## How to explain it: Data & ML

**What it does.**
- Builds the factory panels:
  - the 500-factory demo, which drives the walkthrough;
  - a 50,000-factory panel calibrated to MoSPI IIP, which trains and evaluates the product model.
- Computes 67 monthly features in five pillars.
- Trains a LightGBM model of default within 12 months, explained with SHAP.
- Runs the early-warning rules with an anomaly model.
- Benchmarks the same method on real SBA loans and Polish bankruptcies.

**Why this way.**
- Tabular credit data with missing values and a hard explainability requirement favours gradient-boosted trees
  with TreeSHAP over deep learning.
- Monotone constraints make directional signals behave sensibly, for example more bounces can only lower the
  score.
- Real and synthetic results are kept apart because no public Indian MSME dataset links operating data to
  loan outcomes.

**Key files.**
- Synthetic data: `data_gen/generate.py` (demo), `data_gen/engine.py` (full panel), `data_gen/calibrate.py`
- Features: `ml/features.py`
- Models: `ml/train.py` (demo), `ml/train_full.py` (product model)
- Evaluation: `ml/evaluate.py`, `ml/benchmark_real.py`
- Early warning: `ml/ews.py`, `ml/rules.yaml`

**Likely questions.**
1. *Is the data real?* The product model is trained on synthetic data, calibrated to real MoSPI production
   statistics. The method is validated on real U.S. SBA loans (AUC 0.687, CI 0.658–0.713) and real Polish
   bankruptcies (0.958). Indian accuracy needs a lender pilot on consented data.
2. *How do you avoid leakage?*
   - Every feature uses data up to the scoring month only.
   - An automated audit recomputes features from truncated history.
   - A shuffled-label test runs 8 times and scatters around 0.5.
   - Splits are by time and by factory, so no factory appears in both train and test.
   - In the SBA data we found and removed a leaky field, the loan term.
3. *Why is the demo AUC different from the product AUC?* The demo has 500 factories and 121 test defaults, so
   its interval is wide. The product model uses 50,000 factories and reports 0.848 (0.842–0.854).

**Known limits.** Synthetic uplift is by construction; EWS precision is 0.314 on the synthetic panel; thin-file
units need manual review.

---

## How to explain it: Backend & agents

**What it does.** FastAPI exposes a versioned API (`/v1`) with RFC 9457 errors. An orchestrator (the planner
agent) moves each application through a state machine and delegates to:
- the data agent (tool agent): consented pulls and reconciliation;
- the scoring engine;
- the memo agent: retrieval plus generation, checked by the guard (the review agent);
- the early-warning agent;
- the advisor agent.

Every step is audited on a hash chain. Jobs run through a transactional outbox to Dramatiq workers.

**Why this way.**
- A deterministic state machine keeps the officer in control; agents never decide.
- The LLM only writes prose from engine facts, behind a number guard and a template fallback, so the demo
  needs no keys.
- The outbox guarantees no job is lost or doubled.

**Key files.**
- Orchestrator: `agents/orchestrator.py`
- Agents: `agents/*_agent.py`
- Guard: `agents/guard.py`
- Consent: `agents/providers/consent.py`
- Writer with resilience: `agents/providers/llm.py`
- Audit chain: `api/audit_chain.py`
- Tenancy: `api/tenancy.py`
- Jobs: `api/jobs.py`, `worker/`

**Likely questions.**
1. *What if the LLM is down?* A timeout, circuit breaker and per-bank cap all fall back to the deterministic
   template. The memo is always complete, and the outcome is logged.
2. *How does consent work?*
   - It follows the Account Aggregator artefact: purpose, data types, date range and expiry.
   - Pulls are blocked without an active consent.
   - Revocation stops pulls and deletes stored snapshots.
   - Every event is in the consent ledger.
3. *Who owns the decision?* The credit officer. The RM gets a 403 on approve. The KFS and disbursal belong to
   the lender.

**Known limits.** Mock AA and LOS; the SQLite demo has a reset race (self-healing); live connectors are 🔭.

---

## How to explain it: Frontend & UX

**What it does.** A React app with four persona views:
- RM console and application detail
- credit officer decision
- risk cockpit and governance
- MSME app in English or Hindi

It also has the guided demo, light and dark themes, and keyboard shortcuts.

**Why this way.**
- Calm, dense, explainable screens for bank staff; plain language and Hindi for owners.
- Accessibility is checked automatically: WCAG 2.2 AA contrast and axe in every browser test.

**Key files.**
- Pages: `web/src/pages/`
- Features: `web/src/features/` (application, cockpit, governance, demo)
- Components: `web/src/components/`
- Design tokens: `web/src/styles/tokens.css`
- Translations: `web/src/i18n/`

**Likely questions.**
1. *How do low-literacy owners use it?* Hindi, icons beside every status, plain-language reasons, a 90-day plan
   as a checklist, and WhatsApp-style updates (mock).
2. *Is it accessible?* Contrast is checked in CI and axe runs on every key screen in both themes. Status never
   relies on colour alone.
3. *Where do I see the model's honesty?* Governance → Data & Models: provenance badges, CIs, and the real
   benchmarks kept separate.

**Known limits.** Only English and Hindi; offline support is a PWA shell for assets only.

---

## How to explain it: Deployment & docs

**What it does.**
- One free container (Hugging Face Docker Space; Render fallback) serves the API and the web app.
- CI runs:
  - tests on SQLite and PostgreSQL;
  - web lint, unit and browser tests;
  - security gates: gitleaks, pip-audit, bandit, npm audit, Trivy;
  - Helm and Terraform validation;
  - deployment once everything passes.

**Why this way.**
- ₹0 hosting and one URL.
- The lite profile needs no keys or services.
- The production design (AKS, PostgreSQL, Redis, Key Vault in Central India) is documented and validated but
  deliberately not deployed.

**Key files.** `deploy/huggingface/`, `.github/workflows/ci.yml`, `docs/DEPLOYMENT.md`, `docs/SYSTEM_DESIGN.md`

**Likely questions.**
1. *Is it really free?* Yes: the free CPU tier, about 325 MB of memory measured, no paid APIs.
2. *What if the demo is asleep?* Open it 10 minutes early: it's ready about 7 s after the container starts.
   The backups are the video, `make demo` and the screenshots.
3. *How would it scale to 10 lakh accounts?* Stateless API pods, queue + workers, a partitioned serving table,
   a chunked nightly batch and caching. Autoscaling with Kubernetes and KEDA is designed (🔭).

**Known limits.** Free tiers sleep and change terms; the Azure deployment is design-only.
