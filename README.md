# UdyamPulse

**Credit backed by your production, not your property.**

UdyamPulse is a bank-side decision-intelligence platform that lets banks and NBFCs **underwrite and continuously
monitor MSME manufacturers** on live, consented operating data — GST e-invoices, e-way bills, Account Aggregator
bank cash flows, electricity consumption and ERP data — instead of collateral alone.

Prototype for **Visionet Talent Quest 2026** · Techthon · Track: Data and Decision Intelligence · Theme: BFSI ·
**Team Legit, VIT Bhopal University**.

> Synthetic data only — no real entity data is used anywhere. Every credit decision is made by a human credit
> officer; the system only recommends.

![Architecture](docs/images/architecture.png)

## Run it in one command

Requirements: **Python 3.11+**, **Node 20+**, `make`. No API keys, no cloud account.

```bash
make demo
```

This creates a virtualenv, installs dependencies, then:

1. generates 500 synthetic factories × 24 months (`data_gen/generate.py`)
2. builds the silver and gold layers with DuckDB (`data_gen/lake.py`, `ml/features.py`)
3. trains the LightGBM PD model with SHAP, fairness and drift checks (`ml/train.py`)
4. runs the early-warning back-test (`ml/ews.py`)
5. seeds the demo database (`api/seed.py`)
6. starts the API on `:8000` and the web app on **http://localhost:5173**

Steps 1–5 take about 20 seconds after dependencies are installed. Sign in with one click as any persona
(password `demo123`): `rm1` (relationship manager), `co1` (credit officer), `risk1` (risk), `sharma` (MSME owner).

Alternatives: `docker compose up` (API + web; add `--profile https` for Caddy TLS), or run `make api` and `make web`
in two terminals. `make help` lists every target.

## What you will see (5-minute demo)

| Credit console | Risk cockpit | MSME app (PWA) |
|---|---|---|
| ![Console](docs/images/screenshots/credit_console.jpg) | ![Cockpit](docs/images/screenshots/risk_cockpit.jpg) | ![MSME](docs/images/screenshots/msme_app.png) |

1. **Consent → score.** Sharma Auto Components, Ludhiana scores **723 (Approve)** with top-5 SHAP reasons and pillar bars.
2. **Credit memo in < 1 s** with limit, pricing band, risks, covenants and **policy citations [§x.y]** — every number comes from the engine.
3. **Credit officer approves** (the only role allowed), Key Fact Statement stub appears, LOS stub disburses.
4. **Fast-forward 6 weeks:** the top buyer cuts orders — e-way bills ↓42%, kWh ↓32% → **HIGH alert, "visit + limit review"**.
5. **MSME app:** readiness drops to 626, Prophet cash-flow forecast, 90-day plan (with Hindi), **one-tap consent revocation** that stops data pulls.
6. **Governance:** full audit trail, model card, fairness and drift.

Full script: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). Loan lifecycle: [`docs/images/loan_lifecycle.png`](docs/images/loan_lifecycle.png).

## Results (synthetic hold-out)

| Check | Target | Result |
|---|---|---|
| PD model AUC, out-of-time months 17–24 | ≥ 0.80 | **0.81** (KS 0.49, Brier 0.026) |
| EWS median lead time before SMA-2 | ≥ 60 days | **91 days** (recall 100% on 22 SMA-2 events) |
| Memo generation | < 10 s, ≥ 2 citations, 0 invented numbers | **~0.3 s**, 14 citations, unit-tested number guard |
| Only credit officer can approve; every action audited | ✓ | tested |
| Consent revocation blocks new pulls | ✓ | tested |

Reports: [`ml/MODEL_CARD.md`](ml/MODEL_CARD.md) · [`ml/reports/`](ml/reports/) (metrics, fairness, drift, EWS back-test).

## How it works

- **Data & ML** — DuckDB medallion (bronze → silver → gold), 67 features in five pillars (order book 25%, cash flow 25%,
  production 20%, receivables 15%, compliance 15%), LightGBM PD with time split, TreeSHAP reasons, monotonic mapping to
  the **Factory Health Score (300–900)**: 650+ Approve · 550–649 Watch · < 550 High risk.
- **Early warning** — configurable YAML rules (order loss, cash squeeze, buyer risk, diversion, compliance slip) +
  IsolationForest anomalies → severity → next-best action (call · visit · limit review · restructure).
- **Agents** — orchestrator (loan state machine), data agent (AA consent + reconciliation), credit-memo agent
  (RAG over [`policy/credit_policy.md`](policy/credit_policy.md), PDF export), early-warning agent, MSME advisor agent.
  Semantic Kernel + Azure OpenAI when configured; a deterministic template writer otherwise, so the demo never needs keys.
- **Azure-ready** — every cloud dependency sits behind a Protocol (`LLMProvider`, `SearchProvider`, `DocParser`,
  `ConsentProvider`, `LakeStore`) selected by environment variables. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- **Compliance by design** — RBI Digital Lending Directions 2025, DPDP Act 2023, RBI FREE-AI. See
  [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md).

## Repository layout

```
data_gen/   synthetic generator, CALIBRATION.md, DuckDB lake build
lake/       bronze/ silver/ gold/  (git-ignored, built by make)
ml/         features, train, scoring, ews (+ rules.yaml), forecast, MODEL_CARD.md, reports/
agents/     orchestrator, data, memo, ews, advisor agents; providers/ (LLM, search, consent, lake, doc parser)
api/        FastAPI app, routers, ORM models, auth, audit, seed
policy/     sample bank MSME credit policy (RAG corpus)
web/        React + Vite + Tailwind + Recharts: console, cockpit, MSME PWA, governance
docs/       ARCHITECTURE.md, COMPLIANCE.md, DEMO_SCRIPT.md, openapi.json, images/
tests/      pytest: scoring, EWS rules, consent revocation, roles, memo number guard
```

## API

OpenAPI at http://localhost:8000/docs (exported to [`docs/openapi.json`](docs/openapi.json)). Key endpoints:
`POST /auth/login` · `POST /applications` · `POST|DELETE /applications/{id}/consent` · `POST /applications/{id}/score` ·
`POST /applications/{id}/memo` · `POST /applications/{id}/decision` (credit officer only) · `POST /applications/{id}/disburse` ·
`GET /portfolio` · `GET /alerts` · `POST /alerts/{id}/action` · `POST /sim/advance?days=7` ·
`GET /msme/{factory_id}/readiness` · `GET /audit` (risk only).

## Tests

```bash
make test   # 29 tests
make lint   # ruff + TypeScript
```

## Using Azure OpenAI (optional)

Copy `.env.example` to `.env` and set `UP_LLM_PROVIDER=azure_openai` plus the `AZURE_OPENAI_*` values. The memo and
briefing prose is then written by the model through Semantic Kernel; any output containing a number that is not in the
structured facts is rejected and the template text is used instead.
