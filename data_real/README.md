# Real public data (`data_real/`)

Nothing here is personal data, nothing was scraped past a login, paywall or captcha, and every source has an
open licence (see `docs/DATA_SOURCES.md`). Raw downloads live in `data_real/raw/` and derived files in
`data_real/cache/`; both are gitignored. Committed: the scripts, `checksums.json` (URL, size, SHA-256,
licence, retrieval time), and small samples under `samples/` (each ≤ 1 MB).

```bash
make data-real     # SBA 7(a) FOIA + UCI Polish + MoSPI IIP, then refit data_gen/calibration.yaml
make bench-real    # real-data methodology benchmarks -> ml/reports/real_*_benchmark.{json,md}
```

Reruns are idempotent: a file whose size and checksum match `checksums.json` is skipped, and a partial
download resumes with an HTTP Range request.

## Automated

| Script | Source | Licence |
|---|---|---|
| `fetch_sba.py` | U.S. SBA 7(a) FOIA loans, discovered from `data.sba.gov/data.json` (the CKAN API is retired) | Public domain |
| `fetch_uci.py` | UCI ML Repository dataset 365, Polish companies bankruptcy (Tomczak 2016) | CC BY 4.0 |
| `fetch_india.py` | MoSPI Index of Industrial Production, `api.mospi.gov.in` (no key) | MoSPI dissemination guidelines (GODL-India likely, unconfirmed) |

## Manual (not automated on purpose)

These sources need a login, publish only PDFs, or have no stable file link, so they are never fetched
automatically. **They are not read by the calibration yet**: the default-rate, micro-share and regional
targets keep the design values recorded in `data_gen/calibration.yaml` under `targets`, each with its stated
source. The paths below are where a pilot team would place the files when wiring them in.

| Signal | Where | Save as | Columns |
|---|---|---|---|
| GST collections by state, monthly | GST Council monthly press releases (gstcouncil.gov.in) or data.gov.in (free API key) | `data_real/manual/gst_state_monthly.csv` | `month, state, collection_cr` |
| E-way bills generated, monthly | GSTN monthly statistics releases | `data_real/manual/eway_monthly.csv` | `month, eway_bills_lakh` |
| Industrial power demand | Grid-India / CEA monthly reports (PDF) | `data_real/manual/power_monthly.csv` | `month, energy_met_mu` |
| MSME mix by state and sector | Udyam registration dashboard (udyamregistration.gov.in) | `data_real/manual/udyam_mix.csv` | `state, sector, micro, small, medium` |
| MSME stress and default rates | RBI Financial Stability Report; TransUnion CIBIL–SIDBI MSME Pulse (public summaries) | `data_real/manual/msme_stress.csv` | `period, segment, gnpa_pct` |

The microdata portal (microdata.gov.in) requires registration and is out of scope.
