# Test Plan and Results

## 1. Automated Test Summaries
- **Backend (`make test`):** 164 passed, 7 skipped (130.21s)
- **Frontend (`make test-web`):** 35 passed (2.87s)
- **Browser (`npx playwright test`):** 23 passed, 1 skipped (2.1m)

## 2. Manual Guided Demo Runs (5 Runs)
| Run | Result | Notes |
|---|---|---|
| Run 1 | Pass | No issues. |
| Run 2 | Pass | No issues. |
| Run 3 | Pass | No issues. |
| Run 4 | Pass | No issues. |
| Run 5 | Pass | No issues. |

## 3. Persona and Theme Testing
| Step | Persona | Expected | Result | Notes |
|---|---|---|---|---|
| 1 | Relationship Manager (Light) | Dashboard loads | Pass | |
| 2 | Relationship Manager (Dark) | Dashboard loads, text readable | Pass | |
| 3 | Credit Officer (Light) | Memo view loads | Pass | |
| 4 | Credit Officer (Dark) | Memo view loads | Pass | |
| 5 | Risk Head (Light) | Portfolio view loads | Pass | |
| 6 | Risk Head (Dark) | Portfolio view loads | Pass | |
| 7 | MSME Owner (English) | App loads in English | Pass | |
| 8 | MSME Owner (Hindi) | App loads in Hindi | Pass | |

## 4. Demo Script Walkthrough
| Step | Persona | Expected | Result | Notes |
|---|---|---|---|---|
| 1 | RM (`rm1`) | Request consent and pull data (GST, e-way, bank, power, EPFO). All checks pass. | Pass | |
| 2 | RM | Run scoring. Shows Factory Health Score 742, Approve, PD 0.43%. Signal tabs show 5 reasons. | Pass | |
| 3 | RM | Generate memo. Shows limit ₹3.00 Cr, pricing band, covenants, policy citations. What-if simulator works. | Pass | |
| 4 | Credit officer (`co1`) | Open application, comment, review KFS, confirm, disburse via LOS. RM gets a 403 if they try. | Pass | |
| 5 | RM or risk head | Risk cockpit → Play story. Shows e-way bills −42%, power −32% against 8-week baseline. | Pass | |
| 6 | RM | Open High alert, read briefing, log action. Score falls to 590 (Watch). | Pass | |
| 7 | MSME owner (`sharma`) | Readiness → switch to हिन्दी → 90-day plan → My data → Revoke consent. Banner shows deletion. | Pass | |
| 8 | Risk head (`risk1`) | Governance → Data & Models, then Audit trail → Verify chain. Shows SBA 0.687, Polish 0.958, audit chain intact. | Pass | |