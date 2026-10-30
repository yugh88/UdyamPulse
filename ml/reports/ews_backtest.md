# EWS back-test

| Metric | Value |
|---|---|
| sma2_events_in_window | 22 |
| detected_30d_ahead | 22 |
| recall | 1.0 |
| median_lead_days | 91.0 |
| mean_lead_days | 111.8 |
| p25_lead_days | 61.25 |
| alerted_accounts | 61 |
| precision_sma2_within_6m | 0.279 |
| precision_true_stress | 0.492 |
| alert_rate_per_account_month | 0.0408 |
| min_severity | medium |
| target_median_lead_days_met | True |

## Hero factory (UP-F0001)

| Month | Severity | Rules | Action |
|---|---|---|---|
| 19 | None | – | – |
| 20 | None | – | – |
| 21 | high | order_loss | visit + limit review |
| 22 | medium | cash_squeeze | visit |
| 23 | high | cash_squeeze, compliance_slip | restructure |
