# Presentation outline (the deck is the official submission)

One section per checklist item, in the official order. Screenshots are in `docs/media/slides/` (1920×1080,
light), diagrams in the README (Mermaid). Presenters are proposed: team to confirm (see `docs/TEAM.md`).
Keep every number labelled *synthetic*, *real* or *estimate*, as in the README.

---

### 1 · UdyamPulse: credit backed by your production, not your property
- Team Legit, VIT Bhopal University: members and roles
- Visionet Techthon 2026 · BFSI · Data & Decision Intelligence
- Links: live demo, video, repository

**Visual:** `01-login.png` (personas and the prototype banner) · **Presenter:** Deployment & docs
**Notes:** Open with the tagline. One line on what we built: decision intelligence for MSME manufacturing credit.

### 2 · The problem: stale paper and late warnings
- 8.7 crore MSMEs; only 41% have accessed formal credit (TransUnion CIBIL–SIDBI, Jul 2026)
- About ₹30 lakh crore credit gap (SIDBI); MSMEs are 35.4% of manufacturing (Budget 2026-27)
- Lending runs on last year's statements and collateral
- Stress is noticed at SMA-1/2, months after the signals turned

**Visual:** a simple timeline, "signals turn → SMA-2", with 90 days marked · **Presenter:** Data & ML
**Notes:** One sentence first: small manufacturers are lent to on stale paper and property, and their stress
is spotted too late.

### 3 · Who we serve
- RM, credit officer, risk head, MSME owner: one need each
- Beneficiaries: lenders, MSMEs, their employees, the economy
- Needs → features table (README §3)

**Visual:** four persona cards, plus `02-rm-console.png` · **Presenter:** Frontend & UX
**Notes:** Mention Hindi and plain language for owners.

### 4 · What exists, and the gap
- Collateral + CGTMSE, GST / bank-statement fintech, TReDS, stock statements, informal lenders
- Gap: single source, origination only, black box, or excludes units without property
- UdyamPulse: multi-source, explained, continuous

**Visual:** the comparison table from README §4 · **Presenter:** Data & ML
**Notes:** Be respectful of the alternatives; position us as a tool for the bank, not a competitor to it.

### 5 · How it works: five steps
- Apply → consent & pull → score & explain → memo & decide → monitor
- Each step names who acts

**Visual:** the lifecycle diagram (README §5), `03-score-and-reasons.png` · **Presenter:** Backend & agents
**Notes:** Stress "consented" and "the officer decides".

### 6 · Key features
- Factory Health Score with reasons ✅, credit memo with citations ✅, early warning ✅
- MSME advisor in Hindi ✅, consent ledger ✅, hash-chained audit ✅, what-if ✅, cockpit ✅, guided demo ✅
- Live AA / GST connectors 🔭

**Visual:** `04-credit-memo.png`, `08-early-warning-alert.png`, `09-msme-app-hindi.png` · **Presenter:** Frontend & UX
**Notes:** Status markers on screen; say clearly what is mocked.

### 7 · Innovation
- New approach: operating signals + continuous monitoring, for an underserved need
- Built on India's public digital infrastructure (AA, GST e-invoicing, e-way bills, Udyam)
- Honest by design: the LLM never makes numbers; real and synthetic results are never blended
- 🔭 Federated learning, ULI, IoT signals, voice-first advisor, OCEN

**Visual:** UVP line + three "what's new" icons · **Presenter:** Data & ML
**Notes:** Keep the emerging-tech bonus brief and labelled as future.

### 8 · Architecture and agents
- Frontend → FastAPI → agent layer → data & ML → providers
- Agents in the panel's vocabulary: planner (orchestrator), tool (data), tool + generation (memo), review
  (guard), EWS, advisor
- Communication: REST, outbox → queue, state machine, audit chain, SSE

**Visual:** the architecture and sequence diagrams (README §8) · **Presenter:** Backend & agents
**Notes:** Walk one request end to end: score → job → agents → audit → SSE.

### 9 · Tech stack and why
- LightGBM over deep learning (tabular data, mandatory explainability)
- FastAPI over Django (lean API); DuckDB/Parquet mirrors the Databricks medallion
- SQLite → PostgreSQL with RLS; Redis as an accelerator, never a single point of failure
- FAISS removed: dozens of policy clauses need exact search

**Visual:** the why-this-tool table (README §9), trimmed to 8 rows · **Presenter:** Backend & agents
**Notes:** "Every tool earns its place." Mention one removal as proof.

### 10 · Prototype and progress
- Live demo (free), guided demo in 7 steps, video
- Done / Partial / Future table
- Round 2 changelog in one line per phase

**Visual:** `14-guided-demo.png` + the progress table · **Presenter:** Deployment & docs
**Notes:** Switch to the live demo here if time allows (`docs/DEMO_SCRIPT.md`).

### 11 · Feasibility and plan
- Today: one free container, ready in 7 s, 325 MB measured
- Pilot on Azure Central India: about ₹42,000 a month (*estimate*); production about ₹1–1.7 lakh (*estimate*)
- Roadmap: FIU partner → back-book → validation → 90-day shadow → live

**Visual:** resources table (README §11) · **Presenter:** Deployment & docs
**Notes:** Name the dependencies honestly: the bank as FIU, data agreements, model-risk approval.

### 12 · Testing, validation and results
- 155 backend tests (160 on PostgreSQL + Redis), 23 web unit tests, 21 browser tests with accessibility
  checks; blocking security gates in CI
- Product model AUC 0.848 (0.842–0.854) *synthetic*; unseen sectors 0.81–0.86
- Real benchmarks: SBA 0.687 (0.658–0.713), Polish 0.958
- We caught a leak in public data (loan term) and report the lower, honest number
- User validation: n sessions (team to update)

**Visual:** `12-governance-data-and-models.png` · **Presenter:** Data & ML
**Notes:** The leak story builds trust. Do not round CIs away.

### 13 · Scalability and sustainability
- Stateless API, queue + workers, partitioned PostgreSQL, cache; K8s + KEDA designed (🔭)
- 10 lakh accounts: nightly batch about 18 min in one process, about 5 min on four (*estimate* from the
  measured 915 accounts/s)
- Business model: about ₹500 per memo + ₹50 per account per month (*estimates*); MLOps; green compute

**Visual:** capacity table (`docs/SYSTEM_DESIGN.md`) · **Presenter:** Backend & agents
**Notes:** Say "measured" vs "estimate" explicitly.

### 14 · Risks, security and privacy
- Top 5 risks with mitigations (README §14); all 20 in `docs/LIMITATIONS_AND_RISKS.md`
- Security: argon2id, short tokens, RBAC + branch scope, RLS, encryption, hash chain, CI scans
- Privacy: DPDP consent, revocation with deletion, minimisation, India residency

**Visual:** `13-audit-chain-verified.png` · **Presenter:** Backend & agents
**Notes:** Lead with the biggest risk, synthetic data, and the pilot that answers it.

### 15 · Expected impact
- Memo in seconds (*measured*); 90-day lead on stress (*synthetic*)
- Approval uplift target for thin-file units (*estimate*, pilot to prove)
- Credit-unlocked scenario (*scenario, not a forecast*)

**Visual:** impact table (README §15) · **Presenter:** Data & ML
**Notes:** Every number carries its label on the slide.

### 16 · Who built what
- Member → area → key files → what they will explain
- Each member answers questions on their own area

**Visual:** ownership table (`docs/TEAM.md`) · **Presenter:** each member, in turn
**Notes:** Confirm the split before the deck is final. Rehearse with `docs/QA_PREP.md`.
