# Remaining tasks (18–23 Nov 2026)

Feature freeze **23 Nov**, deadline **25 Nov**. About a third of the effort each.

Each task is done, reviewed and **committed by its owner from their own machine and git identity**. Tick a box
only when its acceptance check passes. Use conventional commit messages, with no AI attribution.

## Yugh Juneja: Tech Lead (critical path)

- [ ] **Y1 · Ship it.** Push `round2-upgrade`, open a PR, get CI green, merge to `main`.
  - **Acceptance:** PR merged; every CI job green on `main`.
  - **Files:** `.github/workflows/ci.yml`
  - **Status:** PR #1 open (18 Nov); CI running.
- [ ] **Y2 · Free public deployment.**
  - **Acceptance:** a public URL opens from a fresh browser with no keys; warm-up under 60 s; the deploy badge
    in the README; free-tier limits verified in `docs/DEPLOYMENT.md`.
  - **Files:** `render.yaml`, `deploy/huggingface/Dockerfile`, `docs/DEPLOYMENT.md`
  - **Status:**
    - Hugging Face Docker Spaces need PRO (402, verified 18 Nov).
    - The Render blueprint and CI deploy hook are committed.
    - Remaining: create the Render service, add the `RENDER_DEPLOY_HOOK` secret and `DEMO_HOST=render`, then
      the smoke test.
    - The "waking up the demo" screen is done.
- [ ] **Y3 · `/system` page** (staff only): live health (API, DB, cache, queue and worker), p50/p95 of the last
  N requests, the last batch run (accounts and accounts/s), the dataset in use, links to benchmarks.
  - **Acceptance:** page reachable from the nav for staff roles; API + browser tests.
  - **Files:** `api/routers/system.py`, `web/src/pages/System.tsx`
- [ ] **Y4 · k6 load test**, mixed read/write, 50 → 300 virtual users against the full stack, cache on vs off.
  - **Acceptance:** p50/p95/p99, error rate and saturation in `docs/PERFORMANCE.md` and on `/system`,
    labelled as laptop numbers.
  - **Files:** `ops/k6/`, `docs/PERFORMANCE.md`
- [ ] **Y5 · Agent hardening.**
  - The review/guard agent checks every memo number against the engine facts and checks that citations exist;
    if either check fails, it blocks the memo or falls back to the template.
  - An agent-trace panel in the application detail (planner → tool calls → review result, with timings).
  - **Acceptance:** tests for a bad number, a missing citation and the trace contents.
  - **Files:** `agents/guard.py`, `agents/memo_agent.py`, `web/src/features/application/`
- [ ] **Y6 · Integrate Aditya's EWS ranker and expected-loss outputs**: alert queue ranked by priority; memo
  shows expected loss and pricing band.
  - **Acceptance:** API tests; UI shows the ranking.
  - **Depends on:** A1, A3 (API contract from Aditya).
- [ ] **Y7 · Security pass**: RBAC tests, rate limits on the public demo, headers, secrets audit, threat model.
  - **Acceptance:** `docs/SECURITY.md` updated; gitleaks clean.
- [ ] **Y8 · Architecture visuals for the deck**: one clean architecture diagram (frontend → backend → data/ML
  → agent layer → LLMs/APIs/cloud) and one agent + communication sequence diagram.
  - **Acceptance:** PNG exports at 1920×1080 in `docs/media/slides/`.
- [ ] **Y9 · Demo reliability.**
  - **Acceptance:** the guided demo runs the 2-minute path 5 times in a row with no errors; reset takes under
    3 s; `docs/DEMO_RUNBOOK.md` covers warm-up, backup video, local fallback and no-Wi-Fi.

## Kinjal Gupta: Product, UX & Validation

- [ ] **K1 · UI polish** across every screen, light and dark: spacing, empty, loading and error states,
  consistent copy, no raw translation keys.
  - **Acceptance:** `npm run check:contrast` and Playwright pass; before/after screenshots.
  - **Files:** `web/src/`
- [ ] **K2 · Hindi review**: natural Hindi, not literal translation; reasons clear for a non-technical owner.
  - **Acceptance:** every string in `web/src/i18n/hi.ts` and `ml/i18n_hi.py` reviewed; changes committed.
- [ ] **K3 · Accessibility**: keyboard navigation, focus states, alt text, reduced motion.
  - **Acceptance:** axe passes; a keyboard-only walkthrough of the demo path.
- [ ] **K4 · Real user validation**: 2–3 sessions (a banker or credit officer, an MSME owner, the Visionet tech
  specialist).
  - **Acceptance:** rows in `docs/VALIDATION.md` with role only, key feedback and what we changed. **Never
    invent sessions or quotes.**
- [ ] **K5 · Guided-demo copy**: short, confident step cards matching the speaker script.
  - **Files:** `web/src/features/demo/DemoGuide.tsx`
- [ ] **K6 · Deck build**: polish the generated PPTX (calm palette, consistent layout, screenshots, readable at
  the back of a room).
  - **Files:** `deck/UdyamPulse_Round2_TeamLegit.pptx`
- [ ] **K7 · Demo video (backup)**: a 2-minute recording of the demo path with voice-over, uploaded unlisted.
  - **Acceptance:** link in the README and the deck.

## Aditya Raj: Data & ML

- [ ] **A1 · EWS alert ranker**: a LightGBM ranker on top of the rule hits.
  - **Acceptance:** precision@k (k = 5 and 10 alerts per RM per week), recall and median lead **before vs
    after**; operating point justified.
  - **Files:** `ml/ews.py`, `ml/reports/`
- [ ] **A2 · Approval-uplift chart**: at a fixed bad rate, approvals with all signals vs a financials-only model
  (synthetic, labelled).
  - **Acceptance:** slide-ready PNG in `docs/media/slides/`.
- [ ] **A3 · Expected loss and pricing**: EL = PD × LGD × EAD with documented LGD assumptions; PD-based pricing
  bands.
  - **Acceptance:** API contract handed to Yugh (Y6).
- [ ] **A4 · SBA approval-time features**: in-fold NAICS-4 encoding, state unemployment at the approval month
  (BLS), lender volume.
  - **Acceptance:** leakage checks re-run; CIs reported whatever the result.
  - **Files:** `ml/benchmark_real.py`
- [ ] **A5 · Leakage story visual**: SBA AUC 0.915 with the leaky loan-term field vs 0.687 honest, plus the
  60-month design note and the shuffled-label check.
  - **Acceptance:** one slide-ready PNG.
- [ ] **A6 · Model card and source of truth**: regenerate reports; reconcile every number in the README and
  the deck.
  - **Acceptance:** `docs/METRICS_SOURCE_OF_TRUTH.md` lists each number → file → measured or estimated →
    synthetic or real.

## Shared, by 23 Nov

- [ ] Timed rehearsal ≤ 9:30 (all three)
- [ ] `docs/SPEAKER_SCRIPT.md` read through by each speaker for their own slides
- [ ] `docs/QA_PREP.md` answers rehearsed by their owners
