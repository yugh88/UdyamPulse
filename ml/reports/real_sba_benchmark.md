# Real-data benchmark: U.S. SBA 7(a) manufacturing loans

**Provenance: Real public data.** Methodology benchmark on real small-business loan outcomes. Not the Indian MSME score.

Dataset: U.S. SBA 7(a) loans, manufacturing (NAICS 31-33), approved FY2010+.

| Test metric | Value (95% bootstrap CI, 1,000 resamples) |
|---|---|
| AUC | 0.687 (0.658–0.713) |
| KS | 0.292 (0.243–0.345) |
| Brier score | 0.025 (0.022–0.027) |
| Test accounts / defaults | 12,736 / 309 (2.4%) |
| Expected calibration error | 0.0161 |

## Precision in the riskiest accounts

| Top | n | Precision | Recall | Lift |
|---|---|---|---|---|
| 1.0% | 127 | 0.055 | 0.023 | 2.27 |
| 5.0% | 637 | 0.071 | 0.146 | 2.91 |
| 10.0% | 1,274 | 0.060 | 0.246 | 2.46 |
| 20.0% | 2,547 | 0.048 | 0.398 | 1.99 |

## By year

| Year | n | Defaults | Rate | AUC (95% CI) |
|---|---|---|---|---|
| 2018 | 3,708 | 128 | 3.5% | 0.7033 (0.665–0.742) |
| 2019 | 3,127 | 79 | 2.5% | 0.6534 (0.598–0.722) |
| 2020 | 2,585 | 44 | 1.7% | 0.6766 (0.608–0.756) |
| 2021 | 3,316 | 58 | 1.8% | 0.6676 (0.602–0.724) |

## Why the fixed-horizon label is the headline

Headline design: Charged off within 60 months of approval; every disbursed loan approved at least 60 months before the data date (active and paid-off loans count as 0).

For comparison, the resolved-only design (Charged off vs paid in full, loans with a final outcome only (the addendum's design; biased for recent cohorts, shown for comparison)) gives test AUC 0.620 (0.598–0.640) on 10,449 loans, but its AUC falls cohort by cohort:

| Year | n | Defaults | AUC |
|---|---|---|---|
| 2018 | 2,914 | 243 | 0.627 |
| 2019 | 2,138 | 173 | 0.6335 |
| 2020 | 1,605 | 81 | 0.602 |
| 2021 | 1,612 | 74 | 0.6304 |
| 2022 | 881 | 84 | 0.6093 |
| 2023 | 679 | 85 | 0.5681 |
| 2024 | 421 | 34 | 0.4182 |
| 2025 | 187 | 7 | too few defaults |
| 2026 | 12 | 0 | too few defaults |

## Hold-out of whole states

Never-seen states CT, MI, NC, OH, OR, TX, UT, WA, test years: AUC 0.681 (0.616–0.748), n = 3,591, defaults = 73.

## Calibration (test, after isotonic calibration on validation)

| Decile | n | Mean predicted | Observed |
|---|---|---|---|
| 1 | 1,126 | 0.0079 | 0.0036 |
| 2 | 1,332 | 0.0163 | 0.0105 |
| 3 | 2,393 | 0.0243 | 0.0100 |
| 4 | 3,556 | 0.0348 | 0.0228 |
| 5 | 2,799 | 0.0459 | 0.0368 |
| 6 | 1,530 | 0.1133 | 0.0542 |

## Strongest features (mean |SHAP|, test)

- `business_age` 0.4372
- `interest_rate` 0.3349
- `log_amount` 0.2163
- `naics4_te` 0.1331
- `lender_volume` 0.1121
- `jobs_supported` 0.0815
- `guarantee_pct` 0.0809
- `state_te` 0.0769
- `processing_method` 0.0678
- `variable_rate` 0.0521

## Limitations

- SBA records a charge-off a median 58 months after approval, so the 60-month label captures roughly the defaults of the first three years; later defaults count as performing.
- The resolved-only design (paid in full vs charged off) scores higher on recent cohorts because their resolved loans are early payoffs and early charge-offs; its AUC falls cohort by cohort, which is why it is not the headline.
- U.S. loans with SBA guarantees differ from Indian MSME credit; only the methodology transfers.
- Lender volume uses the originating lender ID (LocationID); current-servicer fields are excluded.
- Loan term, normally a strong approval-time predictor, is excluded because the published value is revised for loans that go bad (see leakage_guard.term_leakage_evidence). With it the test AUC would read 0.914 (leakage_guard.auc_if_term_included), an inflated figure we do not report.

## Source

- U.S. Small Business Administration, 7(a) & 504 FOIA, https://data.sba.gov · U.S. Government Work (public domain), https://www.usa.gov/publicdomain/label/1.0/ · retrieved 2026-11-17T12:50:46+00:00 · `FOIA_7a_FY2010_FY2019_asof_260930.csv` sha256 39aa32b71fb5dbb4…
- U.S. Small Business Administration, 7(a) & 504 FOIA, https://data.sba.gov · U.S. Government Work (public domain), https://www.usa.gov/publicdomain/label/1.0/ · retrieved 2026-11-17T12:50:55+00:00 · `FOIA_7a_FY2020_Present_asof_260930.csv` sha256 b56194df6da2c22c…
