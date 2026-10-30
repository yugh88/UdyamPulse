# Demo script (under 5 minutes)

**Setup (before the demo):** `make demo` → open http://localhost:5173. To reset at any time: `make seed`
(restarts the clock at 30 Jun 2026). Logins use password `demo123`.

| # | Time | Persona | Do | Say |
|---|---|---|---|---|
| 1 | 0:00 | RM (`rm1`) | Credit console → **Sharma Auto Components, Ludhiana** → *Request consent & pull data* | "Consent comes through the Account Aggregator with a clear purpose. The data agent pulls GST, e-way bills, bank, power and EPFO data and reconciles it — all four checks pass." |
| 2 | 0:40 | RM | *Run scoring* | "Factory Health Score **723 — Approve**, PD 0.67%. Top-5 reasons in plain language, and pillar bars showing exactly how many points each pillar adds or removes. The 24-month chart shows dispatch, power and bank inflow moving together." |
| 3 | 1:20 | RM | *Generate memo* → *Preview PDF* | "The memo agent produced this in **well under 10 seconds**: limit ₹3.00 Cr, pricing EBLR + 2.50–3.00%, strengths, risks, mitigants, covenants and **policy citations** like [§4.1]. Every number comes from the scoring engine — the LLM only writes prose, and a guard rejects invented numbers." |
| 4 | 2:00 | Credit officer (`co1`) | Sign out → Credit officer → open the application → comment → **Approve** → **Disburse via LOS** | "Only the credit officer can decide — the RM gets a 403. Approval generates the **Key Fact Statement** stub; disbursal goes straight to the borrower's account through the LOS stub." |
| 5 | 2:40 | Credit officer / RM | **Risk cockpit** → **+6 weeks** | "We fast-forward six weeks. Sharma's biggest buyer has cut orders: **e-way bills ↓42%, kWh ↓32%** against the 8-week baseline." |
| 6 | 3:10 | RM | Open the **HIGH** alert → read the briefing → *Log: visit + limit review* | "The early-warning agent raised a HIGH alert with reasons and a next-best action — **visit + limit review** within the policy SLA [§8.3]. In back-testing the median alert comes **91 days before SMA-2**." |
| 7 | 3:40 | MSME (`sharma`) | Sign in as MSME → Readiness (score ↓ to **626 Watch**), forecast, **90-day plan** (toggle हिंदी) → **Consent → Revoke** → back to Readiness | "The owner sees the same truth in simple language, with a cash-flow forecast and a 90-day plan. Revoking consent is one tap: data pulls stop immediately and the bank's copies are deleted." |
| 8 | 4:30 | Risk (`risk1`) | **Governance** → audit log, fairness, model card | "Every agent tool call is in the audit log with a hash of its output. Model card: out-of-time AUC 0.81, fairness ratios by sector and micro/small, drift check. Explainable, human-in-the-loop, compliant." |

## Backup: API-only walkthrough

```bash
# terminal 1
make api
# terminal 2
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"username":"rm1","password":"demo123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s localhost:8000/applications -H "Authorization: Bearer $TOKEN"
```
Interactive docs: http://localhost:8000/docs

## Screen-recording checklist

- [ ] `make seed` immediately before recording (clock at 2026-06-30, hero in APPLIED)
- [ ] Browser at 1440×900, zoom 100%, bookmarks bar hidden
- [ ] Steps 1–8 above in one take; pause 1 s on the score, memo summary, HIGH alert, revoke banner
- [ ] Show `make test` passing (29 tests) at the end, or include as a still
- [ ] Mention: synthetic data only, no real entity data; template LLM (no API keys) used in the recording
