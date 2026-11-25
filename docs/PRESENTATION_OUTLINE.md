# 10-minute deck outline

**10 slides · 9:30 of talk + 0:30 buffer · one idea per slide · ≤ 25 words of body text.**
- The footer of each slide lists the checklist items it covers, so the reviewer can tick all 16.
- Speaking time: Yugh about 5:20 (lead), Kinjal 2:25, Aditya 1:50.
- Visuals marked *pending* are produced by the named task in `docs/TASKS.md`.

| # | Slide | Covers | Speaker | Time |
|---|---|---|---|---|
| 1 | UdyamPulse: credit backed by production, not property | 1 | Yugh | 0:20 |
| 2 | The problem, who feels it, why today's tools fail | 2 · 3 · 4 | Kinjal | 1:00 |
| 3 | How UdyamPulse works | 5 · 6 | Yugh | 1:00 |
| 4 | What's new | 7 | Kinjal | 0:40 |
| 5 | Architecture, agents and why each tool | 8 · 9 | Yugh | 1:15 |
| 6 | Live demo | 10 | Yugh drives; Kinjal 0:20 on the MSME app | 2:00 |
| 7 | Tested, validated, honest | 12 | Aditya | 1:00 |
| 8 | Feasible today, scales tomorrow | 11 · 13 | Yugh | 0:50 |
| 9 | Risks, security, privacy, responsible AI | 14 | Aditya | 0:50 |
| 10 | Impact and who built what | 15 · 16 | Kinjal 0:25 → Yugh 0:15 | 0:40 |
| | **Total** | 1–16 | | **9:35** (trim slide 5 by 5 s in rehearsal) |

---

### 1 · UdyamPulse: credit backed by production, not property · footer: *Checklist 1*
- **Body:** Decision intelligence for MSME manufacturing credit. Team Legit, VIT Bhopal: Yugh Juneja (Tech Lead),
  Kinjal Gupta (Product & UX), Aditya Raj (Database, Data Validation & QA).
- **Visual:** logo, three names with roles and programmes, track line, **live demo URL + QR** (*pending Y2*)
- **Speaker (Yugh, 0:20):** one-line pitch; "we'll show it live in a few minutes".

### 2 · The problem, who feels it, why today's tools fail · footer: *Checklist 2 · 3 · 4*
- **Body:** Small manufacturers are judged on stale paper and property; stress is seen too late.
  - 8.7 Cr MSMEs
  - 41% credit-served
  - ₹30 L Cr gap
- **Visual:**
  - three stat tiles with sources;
  - three persona icons (RM, credit officer, MSME owner);
  - a 4-row strip "existing solution → gap": collateral + CGTMSE, GST-scoring fintech, TReDS, stock
    statements.
- **Speaker (Kinjal, 1:00):** problem sentence → who feels it → why current tools fail → "here's what we built",
  handing to Yugh.

### 3 · How UdyamPulse works · footer: *Checklist 5 · 6*
- **Body:** Consent → score → memo → officer decides → continuous monitoring.
- **Visual:**
  - the 5-step flow (`docs/images/lifecycle.png`);
  - five ✅ features: score + reasons, memo with citations, early warning, Hindi MSME app, hash-chained audit.
- **Speaker (Yugh, 1:00):** walk the five steps; stress consent and "the officer decides".

### 4 · What's new · footer: *Checklist 7*
- **Body:** A new approach (operating signals plus continuous monitoring) for an underserved need:
  credit-invisible small manufacturers.
- **Visual:**
  - comparison table: UdyamPulse vs GST-scoring fintechs vs TReDS vs collateral loans, on four rows (signal
    breadth, explainability, monitoring, property needed);
  - 🔭 strip: federated learning, ULI, IoT, voice, OCEN.
- **Speaker (Kinjal, 0:40):** UVP line; why it's new; the emerging-tech ideas labelled future.

### 5 · Architecture, agents and why each tool · footer: *Checklist 8 · 9*
- **Body:** Agents recommend, guard reviews, officer decides. Every tool earns its place.
- **Visual:**
  - architecture diagram (*pending Y8*; interim `docs/images/architecture.png`);
  - agent roles: planner, tool, memo, review, EWS, advisor;
  - 6-row tool → why table: LightGBM, FastAPI, DuckDB/Parquet, PostgreSQL + RLS, Redis + workers, template
    writer.
- **Speaker (Yugh, 1:15):** one request end to end; "the LLM never produces numbers"; FAISS removed as proof
  of justified tools.

### 6 · Live demo · footer: *Checklist 10*
- **Body:** Live: guided demo, Sharma Auto Components. Backup: video link.
- **Visual:** demo URL + QR; backup screenshot `docs/media/slides/28-guided-demo.png`
- **Path (2:00):**
  1. apply → consent → score + reasons;
  2. memo with citations and the agent trace (*pending Y5*);
  3. officer approves → KFS;
  4. play six weeks → HIGH alert;
  5. Kinjal (0:20): MSME app in Hindi → revoke consent.
- **Fallback:** video (*pending K7*) → local `make demo` → screenshots (`docs/DEMO_RUNBOOK.md`, *pending Y9*).

### 7 · Tested, validated, honest · footer: *Checklist 12*
- **Body:** Synthetic and real kept apart. We found a leak in public data and report the honest number.
- **Visual:**
  - results table with CIs:
    - product model 0.848 (0.842–0.854), *synthetic*;
    - SBA 0.687 (0.658–0.713), *real*;
    - Polish 0.954, *real*;
  - leakage chart 0.914 → 0.687 (*pending Y14*);
  - EWS precision@k before/after (*pending Y10*);
  - test counts and CI badge;
  - validation highlights (*pending K5*: only real sessions).
- **Speaker (Aditya, 1:00):** results → the leak story → EWS → "tested in CI on every change".

### 8 · Feasible today, scales tomorrow · footer: *Checklist 11 · 13*
- **Body:** ₹0 today. Pilot about ₹42k/month (estimate). Ten lakh accounts: batch in about 2 minutes in one
  process (estimate).
- **Visual:**
  - path: free container → Azure pilot → production;
  - capacity numbers: measured 8,752 accounts/s; k6 p95 (*pending Y4*);
  - resources and cost (*estimates*);
  - next steps with dates.
- **Speaker (Yugh, 0:50):** measured vs estimate, said out loud; the `/system` page (*pending Y3*).

### 9 · Risks, security, privacy, responsible AI · footer: *Checklist 14*
- **Body:** Human in the loop. LLM never produces numbers. Consent revocable. India residency.
- **Visual:**
  - top 6 risks → mitigation → status (synthetic data, no live AA, LLM failure, alert fatigue, privacy,
    security);
  - DPDP / RBI Digital Lending / FREE-AI badges.
- **Speaker (Aditya, 0:50):** biggest risk first (synthetic data → the pilot answers it); then controls.

### 10 · Impact and who built what · footer: *Checklist 15 · 16*
- **Body:** Memo in seconds (measured). 90-day early warning (synthetic). The ask: a pilot with one lender.
- **Visual:**
  - impact tiles, each labelled measured, estimate or synthetic: memo time, lead time, approval uplift
    (*pending Y11*), ROI example;
  - 3-column ownership strip from `docs/TEAM.md`.
- **Speaker:** Kinjal (0:25) on impact → Yugh (0:15) closes with the ask.

Word-for-word script: `docs/SPEAKER_SCRIPT.md`. Questions by owner: `docs/QA_PREP.md`.
