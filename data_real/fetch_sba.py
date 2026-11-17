"""U.S. SBA 7(a) loan-level FOIA data (public domain): discover, download, convert.

The SBA retired its CKAN API; the agency's DCAT catalogue (`data.sba.gov/data.json`, the federal open-data
standard) still lists every distribution. File names change each quarter, so URLs are discovered from the
catalogue on every run, never hard-coded. Only the FY2010+ 7(a) files and the data dictionary are fetched.

Output: `data_real/cache/sba_7a_fy2010plus.parquet` with every published column except the borrower's name and
street address, city and ZIP, which no part of UdyamPulse needs. Feature selection and leakage control happen
in ml/benchmark_real.py, where they are tested.

    python -m data_real.fetch_sba
"""

from __future__ import annotations

import logging
import re
import time

from data_real.common import CACHE, RAW, download, http_json

CATALOGUE = "https://data.sba.gov/data.json"
DATASET_TITLE = "7(a) & 504 FOIA"
LICENCE = "U.S. Government Work (public domain), https://www.usa.gov/publicdomain/label/1.0/"
SOURCE = "U.S. Small Business Administration, 7(a) & 504 FOIA, https://data.sba.gov"
log = logging.getLogger("udyampulse.data_real.sba")


def discover() -> dict[str, str]:
    """{'dictionary': url, '7a_2010_2019': url, '7a_2020_present': url} from the live catalogue."""
    catalogue = http_json(CATALOGUE)
    dataset = next((d for d in catalogue.get("dataset", []) if d.get("title", "").strip() == DATASET_TITLE), None)
    if dataset is None:
        raise RuntimeError(f"'{DATASET_TITLE}' not found in {CATALOGUE}; the catalogue layout may have changed")
    if "publicdomain" not in str(dataset.get("license", "")):
        raise RuntimeError(f"Unexpected licence {dataset.get('license')!r}; refusing to download")
    found: dict[str, str] = {}
    for dist in dataset.get("distribution", []):
        title, url = dist.get("title", ""), dist.get("downloadURL", "")
        if not url:
            continue
        if "dictionary" in title.lower():
            found["dictionary"] = url
        elif re.search(r"7\(a\)\s*\(FY2010-FY2019\)", title):
            found["7a_2010_2019"] = url
        elif re.search(r"7\(a\)\s*\(FY2020-Present\)", title):
            found["7a_2020_present"] = url
    missing = {"dictionary", "7a_2010_2019", "7a_2020_present"} - set(found)
    if missing:
        raise RuntimeError(f"Catalogue entries not found: {sorted(missing)}")
    return found


def fetch() -> dict[str, str]:
    urls = discover()
    for url in urls.values():
        download(url, RAW / url.rsplit("/", 1)[-1], licence=LICENCE, source=SOURCE)
    return urls


def convert(urls: dict[str, str]) -> str:
    """Both FY2010+ CSVs into one Parquet file with DuckDB (streams; never loads the CSV into pandas)."""
    import duckdb

    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / "sba_7a_fy2010plus.parquet"
    files = [str(RAW / urls[k].rsplit("/", 1)[-1]) for k in ("7a_2010_2019", "7a_2020_present")]
    t0 = time.perf_counter()
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    src = ", ".join(f"'{f}'" for f in files)
    con.execute(f"COPY (SELECT * EXCLUDE (BorrName, BorrStreet, BorrCity, BorrZip) FROM read_csv([{src}], "  # nosec B608
                f"union_by_name = true, all_varchar = true, header = true, ignore_errors = true)) "
                f"TO '{out}' (FORMAT parquet, COMPRESSION zstd)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]  # nosec B608
    log.info("converted %s rows to %s in %.1fs", rows, out.name, time.perf_counter() - t0)
    return str(out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(convert(fetch()))


if __name__ == "__main__":
    main()
