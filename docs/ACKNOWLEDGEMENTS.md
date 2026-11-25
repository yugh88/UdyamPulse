# Acknowledgements and references

Everything UdyamPulse builds on, with credit. Licence inventories are generated from the installed packages:
`docs/licenses/python-runtime.md` (`pip-licenses`) and `docs/licenses/web-direct.md`
(`node web/scripts/licenses.mjs`).

## Problem framing

- **Visionet Systems:** the Techthon 2026 problem statement (BFSI, Data & Decision Intelligence) and the Round 2
  guidelines this project follows.

## Statistics cited in the README and deck

Figures as provided in the team's research brief. Check each against the source document before final
submission, and quote the exact edition.

| Figure | Source |
|---|---|
| 8.7 crore registered MSMEs; 41% have ever accessed formal credit | TransUnion CIBIL–SIDBI *MSME Pulse*, July 2026 |
| About ₹30 lakh crore MSME credit gap | Small Industries Development Bank of India (SIDBI) |
| MSMEs are 35.4% of manufacturing | Union Budget 2026-27 |
| Account Aggregator adoption | Sahamati (AA ecosystem statistics) |
| Informal lenders charge MSMEs about 24% or more | Omidyar Network & BCG, *Credit Disrupted: Digital MSME Lending in India* (2018), as reported by Business Standard (6 May 2019); other studies report higher rates |

## Datasets

| Dataset | Licence | Use |
|---|---|---|
| U.S. Small Business Administration, 7(a) & 504 FOIA loan data | Public domain (U.S. Government Work) | Real-data methodology benchmark |
| Tomczak, S. (2016). *Polish Companies Bankruptcy* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5F600 | CC BY 4.0 | Real-data check of the financial-health pillar |
| Ministry of Statistics and Programme Implementation (MoSPI), Index of Industrial Production | MoSPI dissemination guidelines (GODL-India likely; derived parameters only) | Generator calibration |
| GST Council, RBI, Grid-India / CEA, Udyam portal | Public releases | Identified for calibration; manual steps in `data_real/README.md`, not yet used |

Details, limitations and retrieval checksums: `docs/DATA_SOURCES.md`, `data_real/checksums.json`.

## Regulatory references

- Reserve Bank of India, *Digital Lending Directions*, 2025
- *Digital Personal Data Protection Act*, 2023, and the DPDP Rules, 2025
- Reserve Bank of India, *Framework for Responsible and Ethical Enablement of Artificial Intelligence (FREE-AI)*
- Account Aggregator framework (RBI NBFC-AA Master Direction; Sahamati technical standards)
- RBI framework for early identification of stress (SMA-0/1/2 classification)

## Open-source software

Main libraries and their licences:

| Area | Libraries | Licences |
|---|---|---|
| API | FastAPI, Starlette, Pydantic, Uvicorn, SQLAlchemy, Alembic, PyJWT, httpx | MIT / BSD |
| Data and ML | pandas, NumPy, PyArrow, DuckDB, scikit-learn, LightGBM, Prophet, joblib | BSD / MIT / Apache-2.0 |
| Storage and jobs | psycopg 3 (LGPL-3.0), Redis client (MIT), Dramatiq (LGPL-3.0+) | Used unmodified as libraries, as the LGPL permits |
| Security and observability | cryptography, argon2-cffi, prometheus-client, OpenTelemetry | Apache-2.0 / BSD / MIT |
| Documents | ReportLab | BSD |
| Optional, cloud only | Semantic Kernel (MIT), MLflow (Apache-2.0, training only) | |
| Web | React, React Router, TanStack Query/Table/Virtual, Radix UI, Recharts, Tailwind CSS, Vite, cmdk, sonner, react-i18next | MIT |
| Testing | pytest, Vitest, Testing Library, Playwright, axe-core (MPL-2.0, dev only) | MIT / Apache-2.0 / MPL-2.0 |

## Design

- **Inter** typeface (SIL Open Font License 1.1), via @fontsource
- **Noto Sans Devanagari** (SIL Open Font License 1.1), for Hindi
- **Lucide** icons (ISC)
- Data-visualisation practice: colour-vision-safe palettes, a validated categorical order, a table view for
  every chart
