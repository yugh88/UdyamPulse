# Data strategy

## The constraint we design around

No public dataset contains Indian MSME-level GST, e-way bill, Account Aggregator or electricity data with
loan outcomes. That data is consent-protected (DPDP Act 2023, the Account Aggregator framework) and GST
returns are confidential by law. A credible prototype therefore cannot claim Indian MSME accuracy. It can:

1. show that its **method** works on **real** defaults (Tier A);
2. make its synthetic economy behave like the **real** Indian economy (Tier B);
3. train and stress-test the product on a panel **large enough** for stable metrics and scale testing (Tier C);

and it must label each result with where it came from, never blending them.

## Three tiers

| Tier | What | Real or synthetic | Answers |
|---|---|---|---|
| A | U.S. SBA 7(a) manufacturing loans; UCI Polish bankruptcies | **Real public data** | Do features → LightGBM → calibration → SHAP → monitoring hold up on real defaults? |
| B | MoSPI Index of Industrial Production by NIC division | **Real public data** (aggregate) | Do the synthetic sectors have real seasonality, growth and shock behaviour? |
| C | 50,000 factories × 36 months (`UP_DATASET=full`) | **Synthetic (calibrated)** | Does the product model generalise across factories, sectors, clusters and a shock, and does the system scale? |

The live demo keeps its 500-factory panel (`make demo`, offline, no downloads) so the walkthrough stays fast
and the hero story (Sharma Auto Components, `UP-F0001`) is unchanged. The hero is identical for months 1–24
in every panel size.

## Results, kept apart

### Tier A: real public data (methodology validation)

| Benchmark | Test design | Test AUC (95% CI) | Notes |
|---|---|---|---|
| SBA 7(a), manufacturing | Train FY2010–16, validate FY2017, test FY2018–21; label = charged off within 60 months | **0.687 (0.658–0.713)**; unseen states 0.681 | Approval-time application fields only |
| UCI Polish bankruptcies | Train forecasting years 1–3, test years 4–5 | **0.958 (0.952–0.964)** | Same firm can appear in train and test years |

What the SBA benchmark taught us:

- **A leak in public data.** `TermInMonths` is revised for loans that go bad: 87% of charged-off loans carry a
  non-standard term, against 16% of paid-in-full loans. With it, the AUC was 0.915; without it, 0.687. We
  report the second number, and the evidence is recomputed on every run.
- **A selection bias in the obvious design.** Comparing only paid-in-full and charged-off loans flatters recent
  cohorts, whose resolved loans are early payoffs and early charge-offs. Its AUC falls cohort by cohort, so
  the fixed-horizon label is the headline.
- **The method works, and application data alone is weak.** Calibration on the real outcomes is good (ECE
  0.016) and the state hold-out matches. But approval-time fields predict default only modestly, which is
  exactly the gap operating and cash-flow signals are meant to close.

### Tier C: synthetic (calibrated) product model

50,000 factories × 36 months, 5,045 defaults. Each factory is scored by a model that never saw it or its
test months: 5 factory groups, train months 4–20, validation 21–23, test 25–36. CIs come from a bootstrap
that resamples whole factories.

| Measure (synthetic) | Result |
|---|---|
| Test AUC | **0.848 (0.842–0.854)**; across the 5 groups 0.849 ± 0.006 |
| KS / Brier (calibrated) / ECE | 0.568 / 0.028 / 0.012 |
| Unseen sector (leave one out) | 0.814 (food processing) to 0.864 (textiles) |
| Unseen cluster | 0.831 (Indore) to 0.860 (Ludhiana) |
| Macro shock (trained before it) | before 0.845, during 0.851, recovery 0.841 |
| Ablation: e-way bill, kWh and purchase-order signals | +0.015 AUC (0.009 to 0.020). This reflects how the generator was built and must be re-proven in a pilot |
| Leakage audit | Features recomputed from history cut at the scoring month match: passed |
| Shuffled labels, 8 runs, unconstrained | mean 0.466, runs on both sides of 0.5: passed |
| Domain priors alone (monotone constraints, shuffled labels) | mean 0.662: the economic directions carry real signal by themselves |
| Early warning, chosen operating point (≥ 3 points) | recall 0.866, median lead 90 days, precision 0.314 (was 0.206 at the old threshold) |
| Score bands, default rate | Approve 1.1%, Watch 5.5%, High risk 45.6% |

`make train-full` reproduces all of this in about 11 minutes; the full report is
`ml/reports/full/metrics.json`.

### Demo model (live walkthrough)

500 factories, out-of-time test AUC 0.831 on 121 defaults (an interval of roughly ±0.05). Monotone
constraints (audit M10) raised it from 0.810 and cut overfitting (train AUC 0.995 → 0.967).

## How the synthetic panel is built

- **Calibration (Tier B):** sector seasonality, growth, noise and the 2020 shock shape come from MoSPI IIP. The
  panel's macro shock at month 26 is a demand shock 30% as deep as April 2020, with the same recovery shape.
- **Realism:**
  - Factory random effects.
  - Buyer-network contagion: a large buyer in distress hits its suppliers together, and some buyers default.
  - Five stress types plus sudden defaults.
  - Recoveries and false-alarm dips.
  - Data faults: outages, missing months, outliers, duplicates, late GST filings, GST-vs-bank mismatches.
  - Partial e-invoice coverage below the ₹5 Cr threshold.
- **Targets the addendum set cannot all hold at once:** "at least 5,000 defaults" and "a default rate of 6–9%"
  are incompatible at 50,000 factories. 9% of 50,000 is 4,500. We kept the count: 5,045 defaults, 10.1%
  overall, 12.6% for micro and 6.3% for small units.
- **Engineering:**
  - Vectorised NumPy in chunks of 5,000 with per-chunk seeds.
  - Bronze written as Parquet partitioned by sector and sorted by factory and month (row-group statistics
    prune months).
  - Silver and gold built with DuckDB and pandas, with features in a process pool.
  - The full panel builds in **2 min 12 s at 4.0 GB peak memory** (target: < 10 min, < 8 GB). The demo
    outputs were verified bit-identical after these changes.

## The pilot path to real Indian data

1. **Partner:** a regulated lender (bank or NBFC) acting as Financial Information User under the Account
   Aggregator framework.
2. **Consent:** borrowers consent per purpose through an AA. UdyamPulse already models consent artefacts,
   expiry, revocation and deletion, with every pull blocked when there is no consent.
3. **Data:** GST returns and e-invoices via GSP, bank statements via AA, and e-way bills and electricity where
   the borrower consents. All of it stays in an Indian region (enforced at start-up and in Terraform).
4. **Back-book first:** score the lender's historical, consented book. Re-learn the coefficients, thresholds
   and monotone directions, then re-prove the production-signal uplift that Tier C can only suggest.
5. **Validation:** independent model validation, fairness review, and a shadow period before any score
   informs a decision. A human credit officer always decides.
