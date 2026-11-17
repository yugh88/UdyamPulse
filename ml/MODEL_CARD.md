# Model card: UdyamPulse PD model (`udyampulse-pd`)

_Generated 2026-11-17 19:55 UTC by `ml/model_card.py` from the reports in `ml/reports/`._

## Intended use
Estimate the probability that an MSME manufacturer defaults (90+ DPD) within 12 months from consented operating data, mapped to a Factory Health Score (300–900) with plain-language reasons. It is a **recommendation to the regulated lender's credit officer**; it never decides or executes credit.

Out of scope: consumer lending, units without consented GST/AA data, any automated rejection. No protected attributes exist in the data or features; sector and cluster are used only for fairness monitoring.

## 1. Product model: synthetic (calibrated) panel

**Provenance: Synthetic (calibrated).** Synthetic (calibrated): 50,000 factories x 36 months. Generator calibrated to MoSPI IIP (data_gen/calibration.yaml). No real entity data.

Design: train months 4-20, validation 21-23 (early stopping, isotonic calibration), gap month 24, test months 25-36, 5 factory groups. Every factory is scored by a model that never saw it or its test months. LightGBM with monotone constraints on 61 features.

| Out-of-time, out-of-group test | Value (95% CI, bootstrap over factories) |
|---|---|
| AUC | 0.848 (0.842–0.854) |
| KS | 0.568 (0.556–0.580) |
| Brier (after isotonic calibration) | 0.028 (0.027–0.029) |
| Rows / factories / defaults | 565,505 / 48,102 / 20,845 (3.69%) |
| AUC across the 5 groups | 0.849 ± 0.006 |
| Expected calibration error | 0.0123 (uncalibrated Brier 0.0288) |
| Operating point (flag when score < 650 (Watch or High risk)) | precision 0.104, recall 0.788, flag rate 27.8% |

Default rate by band: APPROVE 1.08%, HIGH_RISK 45.64%, WATCH 5.54%.

### Generalisation

| Hold-out | AUC (95% CI) | Test rows | Defaults |
|---|---|---|---|
| sector = auto_components | 0.855 (0.842–0.869) | 111,368 | 4236 |
| sector = ceramics | 0.858 (0.842–0.872) | 114,392 | 4224 |
| sector = engineering | 0.841 (0.829–0.853) | 114,141 | 4543 |
| sector = food_processing | 0.814 (0.799–0.827) | 113,256 | 3789 |
| sector = textiles | 0.864 (0.851–0.878) | 112,348 | 4053 |
| cluster = Indore | 0.831 (0.817–0.845) | 106,302 | 3743 |
| cluster = Ludhiana | 0.860 (0.846–0.874) | 105,118 | 3918 |
| cluster = Morbi | 0.849 (0.837–0.860) | 106,220 | 3874 |
| cluster = Pune | 0.833 (0.811–0.856) | 38,020 | 1440 |
| cluster = Rajkot | 0.843 (0.827–0.857) | 104,837 | 4012 |
| cluster = Tiruppur | 0.849 (0.836–0.865) | 105,008 | 3858 |
| before shock (month 25) | 0.845 (0.835–0.857) | 48,102 | 2106 |
| shock (26-30) | 0.851 (0.844–0.859) | 238,558 | 10395 |
| recovery (31-36) | 0.841 (0.830–0.850) | 278,845 | 8344 |

### Ablation: production signals

With e-way bill, kWh and purchase-order features AUC 0.8426, without 0.8277; uplift +0.015 (95% CI +0.009 to +0.020). **On synthetic data this uplift reflects how the generator links production signals to stress. It is a hypothesis to re-prove on a lender's consented data in a pilot, not evidence.**

### Leakage audit

- Features recomputed from history cut at the scoring month match the stored features for 450 factory-months: **passed**.
- Shuffled labels, 8 runs, unconstrained model: mean AUC 0.4659 (runs 0.3642–0.5462): **passed** (should scatter around 0.5).
- Domain priors alone: the same shuffled labels with monotone constraints give mean AUC 0.6615. The economic directions encode real knowledge, as an expert scorecard would.

### Early warning on the full panel

| Alert threshold (points) | Recall | Median lead (days) | Precision (SMA-2 in 6 m) | Accounts alerted |
|---|---|---|---|---|
| ≥ 1 | 0.953 | 92.0 | 0.071 | 30,704 |
| ≥ 2 | 0.938 | 91.0 | 0.206 | 14,631 |
| ≥ 3 | 0.866 | 90.0 | 0.314 | 9,826 |
| ≥ 4 | 0.429 | 61.0 | 0.311 | 5,020 |
| ≥ 5 | 0.217 | 61.0 | 0.369 | 2,133 |
| ≥ 6 | 0.082 | 89.0 | 0.349 | 859 |
| ≥ 7 | 0.007 | 61.5 | 0.444 | 63 |
| ≥ 8 | 0.004 | 61.0 | 0.452 | 31 |
| ≥ 9 | 0.0 | None | 0.0 | 5 |

Chosen (highest precision with median lead >= 60 days and recall >= 0.5): **≥ 3 points**: recall 0.866, median lead 90.0 days, precision 0.314.

### Fairness (pooled test)

#### By sector
| Group | n | Default rate | Approval rate | Approval (non-defaulters) | AUC | AIR | EOR |
|---|---|---|---|---|---|---|---|
| auto_components | 111,368 | 3.8% | 71.5% | 73.6% | 0.8564 | 0.904 | 0.911 |
| ceramics | 114,392 | 3.7% | 68.0% | 69.9% | 0.8595 | 0.859 | 0.865 |
| engineering | 114,141 | 4.0% | 71.7% | 73.8% | 0.8431 | 0.906 | 0.913 |
| food_processing | 113,256 | 3.4% | 79.1% | 80.8% | 0.8216 | 1.0 | 1.0 |
| textiles | 112,348 | 3.6% | 70.7% | 72.7% | 0.8638 | 0.894 | 0.899 |

#### Micro vs small
| Group | n | Default rate | Approval rate | Approval (non-defaulters) | AUC | AIR | EOR |
|---|---|---|---|---|---|---|---|
| micro | 334,594 | 4.7% | 64.9% | 67.1% | 0.8424 | 0.783 | 0.798 |
| small | 230,911 | 2.3% | 82.8% | 84.1% | 0.8342 | 1.0 | 1.0 |

## 2. Demo model (live walkthrough)

**Provenance: Synthetic.** 500 factories × 24 months (`make demo`), trained on months 4–12, validated on 13–15, tested out of time on 17–24. Small: the test set has 121 defaults, so its AUC carries a wide interval (about ±0.05).

| Split | AUC | KS | Brier | Rows | Event rate |
|---|---|---|---|---|---|
| Train | 0.9666 | 0.82 | 0.0145 | 4479 | 2.99% |
| Out-of-time test | **0.8314** | 0.5026 | 0.0259 | 3855 | 3.14% |

Hero factory UP-F0001 at month 20: score **742** (APPROVE), PD 0.43%.

Drift: score PSI 0.0103 (stable).

Fairness by sector:

| Group | n | Default rate | Approval rate | Approval (non-defaulters) | AUC | AIR | EOR |
|---|---|---|---|---|---|---|---|
| auto_components | 795 | 2.9% | 87.9% | 89.0% | 0.785 | 0.993 | 0.987 |
| ceramics | 801 | 2.4% | 85.3% | 86.7% | 0.8936 | 0.964 | 0.962 |
| engineering | 800 | 5.0% | 88.5% | 90.1% | 0.7833 | 1.0 | 1.0 |
| food_processing | 580 | 4.1% | 79.7% | 82.2% | 0.9105 | 0.9 | 0.912 |
| textiles | 879 | 1.7% | 82.2% | 83.5% | 0.9488 | 0.929 | 0.926 |

## 3. Real public benchmarks (methodology validation, not the Indian MSME score)

Same pipeline (features → LightGBM → isotonic calibration → SHAP → drift monitoring) on real outcomes. These numbers are **never blended** with the synthetic results above.

| Dataset | Licence | Test AUC (95% CI) | KS | Brier | Test n / defaults |
|---|---|---|---|---|---|
| U.S. SBA 7(a) manufacturing loans, FY2018–21 test | Public domain | 0.687 (0.658–0.713) | 0.292 | 0.0245 | 12,736 / 309 |
| UCI Polish bankruptcies, years 4–5 test | CC BY 4.0 (Tomczak 2016) | 0.954 (0.948–0.960) | 0.751 | 0.0265 | 15,702 / 925 |

SBA: Charged off within 60 months of approval; every disbursed loan approved at least 60 months before the data date (active and paid-off loans count as 0). Loan term was excluded after our leakage audit showed it is revised for loans that go bad. Approval-time application fields alone predict default only modestly, which is the case for operating and cash-flow signals. Details: `ml/reports/real_sba_benchmark.md`.

Polish: The dataset has no company identifier, so the same firm can appear in a training year and a test year; that overlap can flatter the AUC. Details: `ml/reports/real_polish_benchmark.md`.

## Limitations
- The product model is trained on synthetic data. Coefficients, thresholds and the production-signal uplift must be re-learned and re-proven on a lender's consented data, followed by independent model validation.
- Synthetic results reflect the generator's design; the real benchmarks validate the method, not Indian MSME accuracy.
- Monthly granularity; weekly e-way bill and kWh signals would shorten detection lag.
- Thin-file units (< 6 months of data) should be routed to manual review.

## Governance
SHAP reasons on every score, human decision, customer AI disclosure, review route, hash-chained audit trail, fairness and drift checks per training run (RBI FREE-AI principles).
