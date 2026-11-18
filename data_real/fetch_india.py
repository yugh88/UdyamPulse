"""Tier B: real Indian public statistics used to calibrate the synthetic generator.

Automated (public link, no login): MoSPI Index of Industrial Production, monthly, by NIC division
(api.mospi.gov.in, paged at 200 records). Cached as tidy Parquet with source_url, licence and retrieved_at.

Not automated (login, no stable file link, or PDF-only releases): GST collections by state, e-way bill
statistics, industrial power demand, Udyam registration mix, MSME stress rates. Their manual steps are in
data_real/README.md; when the files are absent the generator keeps its documented fallback ranges and says so.

    python -m data_real.fetch_india
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import pandas as pd

from data_real.common import CACHE, http_json, save_checksum, sha256

IIP_URL = "https://api.mospi.gov.in/api/iip/getIIPMonthly"
IIP_LICENCE = ("MoSPI official statistics, disseminated under MoSPI's Guidelines for Statistical Data "
               "Dissemination; GODL-India is the likely licence but was not confirmed for this API. Used only "
               "to derive aggregate calibration parameters; the raw series is not redistributed.")
IIP_SOURCE = "Ministry of Statistics and Programme Implementation (MoSPI), Index of Industrial Production"
log = logging.getLogger("udyampulse.data_real.india")


def fetch_iip(page_size: int = 200, pause: float = 0.1) -> str:
    out = CACHE / "iip_monthly.parquet"
    rows: list[dict] = []
    page, pages = 1, 1
    while page <= pages:
        d = http_json(f"{IIP_URL}?limit={page_size}&page={page}")
        rows += d.get("data", [])
        pages = int(d.get("meta_data", {}).get("totalPages", page))
        page += 1
        time.sleep(pause)
    df = pd.DataFrame(rows)
    df["index"] = pd.to_numeric(df["index"], errors="coerce")
    df["growth_rate"] = pd.to_numeric(df["growth_rate"], errors="coerce")
    df["source_url"] = IIP_URL
    df["licence"] = IIP_LICENCE
    df["retrieved_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    save_checksum(out.name, {"url": IIP_URL, "bytes": out.stat().st_size, "sha256": sha256(out),
                             "licence": IIP_LICENCE, "source": IIP_SOURCE, "rows": len(df),
                             "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                             "note": "checksum of the tidy Parquet; the API serves the latest revision"})
    log.info("IIP: %s records over %s pages", len(df), pages)
    return str(out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(fetch_iip())


if __name__ == "__main__":
    main()
