# Nightly batch throughput (50,000-factory panel, synthetic data)

Measured 2026-11-25T13:27:48+00:00 on Apple M3 Pro, 11 cores, Darwin 25.6.0, Python 3.11.13, commit 2394541. Re-run with `UP_DATASET=full python -m ml.bench_perf`.

| Processes | Accounts | Accounts per second (median) | Wall time (median) | Runs |
|---|---|---|---|---|
| 1 | 46,120 | 8,752 | 5.27 s | 3 |
| 4 | 46,120 | 6,445 | 7.156 s | 3 |

The 10 lakh-account nightly run quoted in the docs is extrapolated from these rates (an estimate).
