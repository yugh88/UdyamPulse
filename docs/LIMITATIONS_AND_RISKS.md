# Limitations and risks

Every known limitation, why it matters, how we handle it, and its status in this prototype.
✅ Done (built and tested) · 🟡 Partial (built in part, or built but unproven) · 🔭 Future (designed, not built).
Owners are proposed and marked "team to confirm" (see `docs/TEAM.md`).

## Top 5 Risks 

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| **1. Synthetic training data** | Real-world accuracy of the Indian MSME score is unproven. | Generator calibrated to MoSPI IIP. Method checked on real U.S. SBA loans (AUC 0.687, 0.658–0.713) and real Polish bankruptcies (0.954, 0.948–0.960). Results are labelled real or synthetic, never blended. A 90-day lender pilot on consented data. | 🟡 Calibration and benchmarks done; pilot 🔭 |
| **2. No live Account Aggregator or GST access** | Live pulls need a regulated entity (FIU), so data is mocked until a bank partners. | Provider interfaces with sandbox mocks. The consent flow follows the AA consent-artefact structure. The partner bank acts as FIU in a pilot. | 🟡 Mock ✅, live 🔭 |
| **3. LLM hallucination or outage** | A wrong number in a credit memo, or a stalled workflow. | The LLM only rewrites prose; numbers come from the engines. A guard rejects any figure not in the facts. Timeout, circuit breaker and template fallback. The demo needs no LLM key. | ✅ |
| **4. Alert fatigue (early-warning false positives)** | RMs stop reading alerts. | Severity tiers and a threshold chosen by sweep. At ≥ 3 points: recall 0.866, median lead 90 days, precision 0.314 (synthetic, `ml/reports/full/metrics.json`), against precision 0.206 at ≥ 2 points. The RM's action and outcome are logged. | ✅ (synthetic numbers) |
| **5. Privacy and regulation (DPDP Act 2023, RBI Digital Lending Directions 2025)** | Legal exposure and loss of trust. | Consent ledger with revocation and deletion, purpose limitation, data minimisation, India-region guard, PII masking, field encryption, hash-chained audit. The lender owns decisions, the KFS and grievance redressal. | ✅ Prototype controls; lender process 🔭 |

---

## Remaining Risks & Limitations

| # | Limitation / risk | Why it matters | Mitigation (how we overcome it) | Status | Owner (proposed) |
|---|---|---|---|---|---|
| 6 | **Electricity data is uneven** across DISCOMs; some bills are paper. | A missing signal must not break scoring. | Power is optional. LightGBM handles missing values natively, and the generator includes missing months and multi-month source outages. OCR of uploaded bills is stubbed (`agents/providers/docparser.py`). | 🟡 Missing-data handling ✅, OCR 🔭 | Data & ML |
| 7 | **Borrower gaming:** fake invoices, circular trading. | Inflated turnover leads to over-lending. | Cross-source reconciliation (GST vs bank credits vs e-way bills vs power), a diversion rule (> 25% mismatch), an IsolationForest anomaly signal, and mismatch flags shown to the officer. | ✅ | Data & ML |
| 8 | **Thin-file / new MSMEs** (cold start). | Fewer than 6 months of history gives weak windows. | Features use whatever history exists, and missing values are native. The advisor's 90-day plan builds a track record. A lower-confidence badge and routing to manual review are recommended in the model card but not yet in the UI. | 🟡 | Data & ML |
| 9 | **Model risk, drift and bias.** | Silent degradation or unfair outcomes. | Time + factory-group split, isotonic calibration, monotone constraints (audit M10), a PSI drift report, fairness ratios by sector and size, a model card, a leakage audit and shuffled-label test, and the officer as final decision-maker. Champion/challenger and a scheduled retraining cadence are designed, not automated. | 🟡 Checks ✅, automation 🔭 | Data & ML |
| 10 | **Security threats on a financial app.** | Data theft or tampering. | RBAC plus branch scope, tenant isolation with PostgreSQL row-level security, argon2id passwords, 15-minute tokens with rotating refresh cookies, rate limits, input validation, security headers and CSP, hash-chained audit, blocking CI scans (gitleaks, pip-audit, bandit, npm audit, Trivy), and a threat model (`docs/THREAT_MODEL.md`). | ✅ | Backend & agents |
| 11 | **Integration with legacy bank systems** (LOS / CBS). | Pilots stall on integration. | REST API with OpenAPI docs; LOS stubbed (disbursement reference); a Dynamics 365 connector path; phased integration starting read-only. | 🟡 API ✅, connectors 🔭 | Backend & agents |
| 12 | **Scale and cost at bank level** (10 lakh accounts). | A slow nightly batch or cockpit. | Stateless API, queue + workers, a chunked and checkpointed batch, cached and indexed portfolio reads, a month-partitioned serving table, measured benchmarks. Kubernetes autoscaling is a design artefact (Helm/Terraform validated with lint and schema checks, never deployed). | 🟡 Backbone ✅, autoscaling 🔭 | Backend & agents |
| 13 | **Free-tier hosting limits** (sleep, RAM, ephemeral disk). | The demo is asleep or slow when the reviewer opens it. | Single container, ready in about 7 s after start; peak memory about 325 MB through the full story (measured under a 512 MB cap); pre-trained artefacts in the image; fresh seed on every start; a "waking up the demo…" screen; a warm-up step in the demo checklist; backups (video, `make demo`, screenshots). | ✅ Image built and tested locally; public URL pending | Deployment & docs |
| 14 | **Adoption and trust by credit officers.** | A tool nobody uses. | Plain-language reasons, policy citations, a what-if simulator that moves in sensible directions (audit M10), human in the loop, a review route. Training material is to be written with the pilot bank. | 🟡 | Frontend & UX |
| 15 | **Low digital literacy and connectivity** in MSME clusters. | Owners cannot use the app. | Hindi UI, icons and plain language, a PWA offline shell for built assets, WhatsApp-style updates (mock channel), an RM-assisted channel. Voice-first is future. | 🟡 | Frontend & UX |
| 16 | **Team capacity and timeline** (17–25 Nov). | Unfinished core features. | MUST / SHOULD / DESIGN-ONLY tiers, a daily checkpoint, a feature freeze on 23 Nov, 25 Nov kept as buffer. | ✅ Plan in place | All |
| 17 | **Leakage in public data** (found in our audit). | Inflated benchmark claims. | SBA `TermInMonths` is revised for loans that go bad (87% non-standard terms among charge-offs vs 16% otherwise). It is excluded with the evidence recomputed every run. With it, the AUC would have read 0.915. | ✅ | Data & ML |
| 18 | **Benchmark selection bias.** | Overstated real-data results. | The "resolved loans only" design flatters recent cohorts, so the headline uses a fixed 60-month horizon on every disbursed loan. Both are reported. | ✅ | Data & ML |
| 19 | **Synthetic uplift is by construction.** | Overclaiming the value of production signals. | The ablation (+0.015 AUC on synthetic data) is labelled as reflecting the generator's design, to be re-proven in the pilot. | ✅ (labelled) | Data & ML |
| 20 | **Demo reset race on SQLite.** | A background relay pass can error once while tables are recreated. | Transient and self-healing on the next pass; PostgreSQL deployments truncate instead of dropping tables. | 🟡 Known | Backend & agents |