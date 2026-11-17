"""UCI Polish Companies Bankruptcy (dataset 365, CC BY 4.0): download and cache as Parquet.

Citation: Tomczak, S. (2016). Polish Companies Bankruptcy [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5F600

    python -m data_real.fetch_uci
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from data_real.common import CACHE, save_checksum, sha256

DATASET_ID = 365
LICENCE = "CC BY 4.0, https://creativecommons.org/licenses/by/4.0/"
CITATION = ("Tomczak, S. (2016). Polish Companies Bankruptcy [Dataset]. UCI Machine Learning Repository. "
            "https://doi.org/10.24432/C5F600")
log = logging.getLogger("udyampulse.data_real.uci")


def fetch() -> str:
    from ucimlrepo import fetch_ucirepo

    out = CACHE / "polish_bankruptcy.parquet"
    if out.exists():
        log.info("have %s", out.name)
        return str(out)
    ds = fetch_ucirepo(id=DATASET_ID)
    frames = [ds.data.features, ds.data.targets]
    if ds.data.ids is not None:
        frames.insert(0, ds.data.ids)
    import pandas as pd

    df = pd.concat(frames, axis=1)
    df.columns = [str(c) for c in df.columns]
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    save_checksum(out.name, {"url": f"https://archive.ics.uci.edu/dataset/{DATASET_ID}", "bytes": out.stat().st_size,
                             "sha256": sha256(out), "licence": LICENCE, "source": CITATION,
                             "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                             "note": "Parquet re-serialisation of the ucimlrepo download"})
    log.info("cached %s rows x %s columns", *df.shape)
    return str(out)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(fetch())


if __name__ == "__main__":
    main()
