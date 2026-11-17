# Real-data benchmark: UCI Polish companies bankruptcy

**Provenance: Real public data.** Validates the financial-health pillar's approach (cash-flow, liquidity, leverage ratios) on real firms. Not the Indian MSME score.

Dataset: UCI Polish companies bankruptcy (43,405 firm-years, 64 financial ratios).

| Test metric | Value (95% bootstrap CI, 1,000 resamples) |
|---|---|
| AUC | 0.954 (0.948–0.960) |
| KS | 0.751 (0.735–0.776) |
| Brier score | 0.026 (0.024–0.029) |
| Test accounts / defaults | 15,702 / 925 (5.9%) |
| Expected calibration error | 0.0142 |

## Precision in the riskiest accounts

| Top | n | Precision | Recall | Lift |
|---|---|---|---|---|
| 1.0% | 157 | 1.000 | 0.170 | 16.98 |
| 5.0% | 785 | 0.710 | 0.602 | 12.04 |
| 10.0% | 1,570 | 0.461 | 0.782 | 7.82 |
| 20.0% | 3,140 | 0.257 | 0.871 | 4.36 |

## By year

| Year | n | Defaults | Rate | AUC (95% CI) |
|---|---|---|---|---|
| 4 | 9,792 | 515 | 5.3% | 0.9557 (0.948–0.963) |
| 5 | 5,910 | 410 | 6.9% | 0.9535 (0.943–0.962) |

## Calibration (test, after isotonic calibration on validation)

| Decile | n | Mean predicted | Observed |
|---|---|---|---|
| 1 | 3,777 | 0.0001 | 0.0003 |
| 2 | 2,867 | 0.0010 | 0.0014 |
| 3 | 2,419 | 0.0022 | 0.0054 |
| 4 | 3,432 | 0.0121 | 0.0186 |
| 5 | 1,536 | 0.0192 | 0.0632 |
| 6 | 1,671 | 0.3724 | 0.4464 |

## Strongest features (mean |SHAP|, test)

- `A27` 0.7885 — profit on operating activities / financial expenses
- `A34` 0.6545 — operating expenses / total liabilities
- `A58` 0.4626 — total costs /total sales
- `A46` 0.4506 — (current assets - inventory) / short-term liabilities
- `A5` 0.4408 — [(cash + short-term securities + receivables - short-term liabilities) / (operating expenses - depreciation)] * 365
- `A24` 0.3024 — gross profit (in 3 years) / total assets
- `A13` 0.2506 — (gross profit + depreciation) / sales
- `A39` 0.2482 — profit on sales / sales
- `A29` 0.2299 — logarithm of total assets
- `A26` 0.2283 — (net profit + depreciation) / total liabilities
- `A33` 0.2216 — operating expenses / short-term liabilities
- `A42` 0.2197 — profit on operating activities / sales

## Limitations

- Polish firms 2000-2013 with audited statements; Indian MSMEs often lack audited accounts, which is why UdyamPulse relies on GST, bank and operating signals instead.
- The dataset has no company identifier, so the same firm can appear in a training year and a test year; that overlap can flatter the AUC.
- Bankrupt firms are 4.8% of rows across a 1-5 year horizon; published studies on this dataset report AUCs of a similar order with gradient boosting.

## Source

- Tomczak, S. (2016). Polish Companies Bankruptcy [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5F600 · CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ · retrieved 2026-11-17T12:52:42+00:00 · `polish_bankruptcy.parquet` sha256 d3dfa85179dd7c5b…

Citation: Tomczak, S. (2016). Polish Companies Bankruptcy [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5F600
