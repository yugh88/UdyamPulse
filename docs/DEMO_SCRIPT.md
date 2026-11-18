# Demo script (under 5 minutes)

**Setup:**
- Open the live link 10 minutes before presenting, to wake a sleeping free instance.
- Locally, run `make demo` and open http://localhost:5173.
- On the login page, click **Guided demo**. Each step signs in the right persona and opens the right screen.
  Step 1 offers **Reset demo data first**.
- Every password is `demo123`. All numbers on screen come from synthetic data.

| # | Time | Persona | Do | Say |
|---|---|---|---|---|
| 1 | 0:00 | RM (`rm1`) | Credit console → **Sharma Auto Components, Ludhiana** → *Request consent and pull data* | "Consent comes through an Account Aggregator style artefact with a stated purpose. The data agent pulls GST, e-way bills, bank, power and EPFO data and reconciles them; all checks pass." |
| 2 | 0:40 | RM | *Run scoring*, then open the signal tabs | "Factory Health Score **742, Approve**, PD 0.43%. Five reasons in plain language and the points each pillar adds or removes. Monotone constraints mean worse signals can only lower a score." |
| 3 | 1:15 | RM | *Generate memo* → open a policy citation → *What-if simulator* | "The memo is drafted in seconds: limit ₹3.00 Cr, pricing band, strengths, risks, covenants and **policy citations**. Every number comes from the engines; a guard rejects invented numbers. The simulator is read-only and labelled." |
| 4 | 2:00 | Credit officer (`co1`) | Open the application → comment → *Review Key Fact Statement* → confirm → *Disburse via LOS* | "Only the credit officer can decide; the RM gets a 403. Approval issues the KFS stub; disbursal goes to the borrower's own account through the LOS stub." |
| 5 | 2:40 | RM or risk head | **Risk cockpit** → *Play story* (six weeks) | "Sharma's biggest buyer cut orders: **e-way bills −42%, power −32%** against the 8-week baseline." |
| 6 | 3:10 | RM | Open the **High** alert → read the briefing → *Log action: visit + limit review* | "A High alert with reasons and a next-best action. The score has fallen to **590 (Watch)**. On our 50,000-factory synthetic back-test, alerts come a median **90 days before SMA-2** at precision 0.314." |
| 7 | 3:45 | MSME owner (`sharma`) | Readiness → switch to **हिन्दी** → 90-day plan → *My data → Revoke consent* | "The owner sees the same truth in simple language, with a cash-flow forecast and a 90-day plan. Revoking consent is one tap: pulls stop immediately and the bank's copy is deleted." |
| 8 | 4:25 | Risk head (`risk1`) | **Governance → Data & Models**, then **Audit trail → Verify chain** | "Real public benchmarks (SBA loans AUC 0.687, Polish bankruptcies 0.958) are kept apart from synthetic results (product model 0.848, CI 0.842–0.854). Every action is on a tamper-evident audit chain: Verify shows it intact." |

**Close (5:00):** "Credit backed by your production, not your property. The bank decides; we make the decision
faster, explainable and continuously informed. Next: a pilot with one lender on consented data."

## Backup: API only

```bash
make api      # then, in another terminal:
TOKEN=$(curl -s localhost:8000/v1/auth/login -H 'content-type: application/json' \
  -d '{"username":"rm1","password":"demo123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s localhost:8000/v1/applications -H "Authorization: Bearer $TOKEN"
```

Interactive docs: http://localhost:8000/docs

## Recording checklist

- [ ] Reset the demo (Guided demo → step 1 → *Reset demo data first*, or `make seed`)
- [ ] Browser at 1440×900 or 1920×1080, zoom 100%, bookmarks bar hidden, light theme
- [ ] Steps 1–8 in one take; pause 1 s on the score, the memo, the High alert, the revoke banner and Verify chain
- [ ] Say once: synthetic data only, no real entity; no API keys (the template writer is used)
- [ ] Optional still at the end: CI green, with the test counts from README §12
