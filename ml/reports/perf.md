# Performance benchmarks (demo panel, synthetic data)

Measured 2026-11-25T13:32:54+00:00 on Apple M3 Pro, 11 cores, Darwin 25.6.0, Python 3.11.13, commit 2394541. Re-run with `python -m ml.bench_perf`.

| What | Median | Runs | Notes |
|---|---|---|---|
| Nightly batch, accounts scored per second (one process) | 6,004 | 5 | 478 accounts, month 24, wall 0.08 s |
| Portfolio read, `GET /v1/portfolio` | 19.9 ms | 15 | SQLite, read cache off |
| Credit memo drafted (template writer) | 16 ms | 5 | hero application, including the PDF |
| Demo reset, `POST /v1/demo/reset` | 1,707 ms | 5 | |

Estimates derived from these numbers (for example the 10 lakh-account nightly run) are labelled as estimates where they are quoted.
