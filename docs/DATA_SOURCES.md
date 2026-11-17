# Data sources

Every dataset UdyamPulse uses, its licence, how it is used and what it cannot tell us. Two rules hold
throughout:

- No scraped, bought, leaked or login-gated data, and no personal data.
- Real and synthetic results are always reported separately, never blended into one number.

Retrieval times, sizes and SHA-256 checksums are in `data_real/checksums.json`.

## Real public data

### U.S. Small Business Administration: 7(a) & 504 FOIA loan data

- **Source:** https://data.sba.gov, dataset "7(a) & 504 FOIA". File URLs are discovered at run time from the
  agency's DCAT catalogue (`https://data.sba.gov/data.json`); the CKAN API cited in older guides is retired.
- **Licence:** U.S. Government Work, public domain (https://www.usa.gov/publicdomain/label/1.0/).
- **Attribution:** U.S. Small Business Administration.
- **Used:** the FY2010–2019 and FY2020–present 7(a) files, filtered to manufacturing (NAICS 31–33).
  - The borrower's name, street, city and ZIP are dropped at conversion and never stored.
- **Use:** methodology benchmark on real loan defaults (`ml/benchmark_real.py`, `ml/reports/real_sba_benchmark.md`).
  - **Headline label:** charged off within 60 months of approval, on every disbursed loan approved at least
    60 months before the data date.
  - **Comparison:** the "resolved loans only" design is reported beside it.
- **Limitations:**
  - U.S. guaranteed loans are not Indian MSME credit; only the method transfers.
  - Charge-offs are recorded a median 58 months after approval.
  - `TermInMonths` is revised for loans that go bad, so it is excluded as leakage. The evidence is in the report.

### UCI Machine Learning Repository: Polish Companies Bankruptcy (dataset 365)

- **Source:** https://archive.ics.uci.edu/dataset/365, via `ucimlrepo`.
- **Licence:** CC BY 4.0 (stated on the dataset page).
- **Citation:** Tomczak, S. (2016). *Polish Companies Bankruptcy* [Dataset]. UCI Machine Learning Repository.
  https://doi.org/10.24432/C5F600
- **Use:** checks that the financial-health pillar's approach (liquidity, leverage, profitability and activity
  ratios) separates real failures (`ml/reports/real_polish_benchmark.md`). The committed sample is the
  ratio definitions only (`data_real/samples/polish_variables.json`).
- **Limitations:**
  - Audited statements of Polish firms, 2000–2013.
  - No company identifier, so the same firm may appear in both training and test years.

### Ministry of Statistics and Programme Implementation (MoSPI): Index of Industrial Production

- **Source:** https://api.mospi.gov.in (`/api/iip/getIIPMonthly`, public, no key), 17,196 monthly records.
  The generator is fitted on the base 2011-12 series of five NIC divisions:
  - Motor vehicles, trailers and semi-trailers
  - Machinery and equipment n.e.c.
  - Textiles
  - Other non-metallic mineral products
  - Food products
- **Licence:** MoSPI official statistics, disseminated under MoSPI's Guidelines for Statistical Data
  Dissemination. The Government Open Data License – India is the likely licence, but we could not confirm
  it for this API. We therefore publish only derived parameters (seasonal indices, growth rates, shock
  depth and recovery), never the raw series.
- **Use:** Tier B calibration of the synthetic generator (`data_gen/calibrate.py` → `data_gen/calibration.yaml`).
  - Sector seasonality, trend growth and monthly noise.
  - The shape of the macro shock: April 2020 vs April 2019, and months to recover to 95%, scaled to 30%.
- **Limitations:** a national, sector-level index. It says nothing about individual firms, regions or credit
  outcomes.

### Identified but not automated

GST collections by state, e-way bill statistics, Grid-India / CEA power demand, the Udyam registration
dashboard, and RBI / TransUnion CIBIL–SIDBI MSME stress summaries. None of them publishes a stable,
machine-readable file without a login or PDF extraction. Manual steps are in `data_real/README.md`. The
calibration does not read them yet; the corresponding targets carry design values with their stated source.

## Synthetic data

| Panel | Built by | Size | Use |
|---|---|---|---|
| Demo | `data_gen/generate.py` (seed 42) | 500 factories × 24 months | `make demo`, the live walkthrough and its model |
| Full | `data_gen/engine.py`, calibrated as above | 50,000 × 36 = 18 lakh factory-months | Product model training and evaluation |
| Scale | same engine | 1,00,000 × 36 | Performance benchmarks only |

- No real entity appears anywhere: names, Udyam numbers (`UDYAM-SYN-…`) and every signal are generated.
- No protected attributes (gender, religion, caste, age) exist in any dataset.
- The hero factory, Sharma Auto Components (`UP-F0001`), is identical for months 1–24 in every panel.

## What real Indian MSME data would need

There is no public Indian dataset of firm-level GST, e-way bill, Account Aggregator or electricity data with
loan outcomes. This data is protected by the DPDP Act 2023, the Account Aggregator framework and GST
confidentiality, and that is how it should be. `docs/DATA_STRATEGY.md` describes the pilot path: a regulated
lender, borrower consent through an Account Aggregator, and a model retrained and independently validated on
that consented data.
