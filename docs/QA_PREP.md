# Q&A preparation: 25 likely panel questions

Short answers, each backed by a file or a measured number. "Synthetic" means it comes from our generated
panel; "real" means public data. Never blend the two in an answer.

## Problem and users

**1. What problem are you solving, in one sentence?**
Credit-invisible small manufacturers are judged on stale paper and collateral, and their stress is found
too late. UdyamPulse scores them on consented, live operating data and keeps watching after disbursal.

**2. Who uses it?**
- the relationship manager, who scores and monitors;
- the credit officer, who decides;
- the risk head, who sees the portfolio and governance;
- the MSME owner, who sees readiness, a 90-day plan in Hindi, and controls consent (`docs/USERS.md`).

**3. How is this different from GST-based fintech lenders?**
- They score one source at origination. We reconcile GST, e-way bills, bank inflows, power and EPFO
  (catching inflated invoices).
- We explain every score in plain language.
- We keep monitoring after disbursal, with an early warning about 90 days before SMA-2 (synthetic back-test).
- We are a decision tool for the bank's officer, not an automated lender.

**4. What did you validate with real users?**
See `docs/VALIDATION.md`. We record only real sessions, with roles only. Say the current count honestly.

## Data and models

**5. Why synthetic data?**
There is no public Indian dataset linking firm-level GST, AA or power data to loan outcomes. That data is
protected by the DPDP Act and the AA framework. We calibrate the generator to real MoSPI production
statistics and validate the method on real public defaults.

**6. So what is real?**
- U.S. SBA 7(a) manufacturing loans: test AUC 0.687 (95% CI 0.658–0.713), approval-time fields only.
- UCI Polish bankruptcies: 0.954 (0.948–0.960).
- MoSPI IIP calibration data.

**7. How good is the product model?**
On 50,000 synthetic factories, scored out of time and out of group: AUC 0.848 (0.842–0.854). It holds on unseen
sectors (0.81–0.86), unseen clusters (0.83–0.86) and across a macro shock (0.84–0.85). It is calibrated
(ECE 0.012). These are synthetic results; a pilot must prove them on real data.

**8. How do you avoid leakage?**
- Features use data only up to the scoring month.
- An automated audit recomputes features from truncated history and they match.
- 8 shuffled-label runs scatter around 0.5 (mean 0.466).
- Splits are by time and by factory.
- In the SBA data we caught a real leak: the loan term is revised for loans that go bad. With it the AUC reads
  0.914; we report 0.687.

**9. Why LightGBM, not deep learning?**
The data is tabular with missing values, and explainability is mandatory. Gradient-boosted trees give the
best accuracy for the speed, handle missing values natively, and work with exact TreeSHAP reasons. Monotone
constraints keep them sensible.

**10. How do you explain a score?**
The top 5 SHAP reasons in plain language, plus points per pillar. The same reasons appear in Hindi for the
owner. The what-if simulator shows how a change would move the score, and is labelled as a simulation.

**11. Is it fair?**
- No protected attributes exist.
- On every training run we report the adverse impact ratio and equal-opportunity ratio by sector and by
  micro/small (model card).
- Monotone constraints prevent perverse behaviour.

**12. What about drift?**
PSI on the score and the top features: currently stable (synthetic). Retraining cadence and
champion/challenger are designed for the pilot (🔭).

## Early warning

**13. How early, and how noisy?**
On the synthetic 50,000-factory panel, at the chosen operating point:
- recall 0.866;
- median lead 90 days before SMA-2;
- precision 0.314.

We report the whole precision/lead trade-off in the model card, not one flattering number.

**14. What does an RM do with an alert?**
The alert gives the reasons (for example "e-way bills −42%, kWh −32% vs the 8-week baseline"), a severity and
a next-best action such as a visit and limit review. The RM logs the action and its outcome, which feeds back
into evaluation.

## AI and safety

**15. What if the LLM is down, slow or hallucinates?**
- The LLM only rewrites prose; numbers come from the engines.
- A guard rejects any number not in the facts.
- Timeouts, a circuit breaker and a per-bank concurrency cap all fall back to a deterministic template.
- The demo uses no LLM key at all.

**16. Who owns the credit decision?**
The credit officer. Agents recommend; the RM cannot approve (403). The lender owns the KFS, disbursal and
grievance redressal.

**17. How does consent work?**
- AA-style consent artefact (purpose, data types, range, expiry).
- No pull without an active consent.
- Revocation stops pulls immediately and deletes the stored snapshot.
- Everything is in the consent ledger.

**18. What are the regulatory risks?**
- **DPDP Act:** consent, purpose limitation, minimisation, erasure.
- **RBI Digital Lending Directions:** the lender decides, KFS, grievance redressal.
- **Data residency:** India regions only, enforced at start-up.

`docs/COMPLIANCE.md` separates what the prototype implements from what is lender process.

**19. How is it secured?**
- argon2id passwords and 15-minute tokens with rotating refresh cookies.
- RBAC plus branch scope, and bank isolation with PostgreSQL row-level security.
- Field encryption and a hash-chained audit trail.
- Rate limits and a strict CSP.
- Blocking security scans in CI.

See `docs/SECURITY.md` and `docs/THREAT_MODEL.md`.

## Feasibility and scale

**20. How does it scale to 10 lakh accounts per bank?**
- Stateless API pods behind a load balancer.
- Queue + workers for scoring, memos and the batch.
- A month-partitioned serving table.
- A chunked, checkpointed, resumable nightly batch.
- Cached and indexed portfolio reads.

The 50,000-factory panel builds in 2 min 12 s at 4 GB. Kubernetes autoscaling (HPA + KEDA) is designed and
validated, not deployed (🔭).

**21. What does it cost?**
- Prototype: ₹0 (free container host, no paid APIs).
- Pilot: about ₹42,000 a month on Azure (estimate).
- Production: about ₹1–1.7 lakh a month for 10 lakh accounts (estimate).

See `docs/DEPLOYMENT.md`.

**22. What is the business model?**
About ₹500 per credit memo plus ₹50 per monitored account per month, charged to the lender. These are
estimates for discussion, not validated pricing.

**23. What's done vs future?**
- **Done:** the demo flow end to end, scoring, memo, early warning, consent, audit, governance, free
  deployment image, tests and CI.
- **Partial:** live AA and GST access (mocked), the public URL (pending the team's account).
- **Future:** Azure deployment, live connectors, federated learning, more languages.

Every claim in the README carries ✅ / 🟡 / 🔭.

## Team

**24. What did each member build?**
See `docs/TEAM.md` (team to confirm). Each member explains their own area.

**25. What would you do with three more months?**
1. A pilot with one lender, as AA FIU, on its consented back-book: re-learn the model, re-prove the
   production-signal uplift, independent validation.
2. Live AA and GSP connectors.
3. Champion/challenger and monitoring dashboards in production.
