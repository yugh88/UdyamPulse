"""Build a whole synthetic dataset (bronze → silver → gold) and record runtime and peak memory.

    UP_DATASET=full python -m data_gen.build     # make data-full
    UP_DATASET=scale python -m data_gen.build    # 1,00,000 factories, for the performance benchmark

Writes `<lake>/build_stats.json`, which the System page and docs/DATA_STRATEGY.md report.
"""

from __future__ import annotations

import json
import logging
import resource
import sys
import time

from core.settings import get_settings


def _mb(who: int) -> int:
    rss = resource.getrusage(who).ru_maxrss
    return round(rss / 2**20 if sys.platform == "darwin" else rss / 1024)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    s = get_settings()
    t0 = time.perf_counter()
    if s.dataset == "demo":
        from data_gen import generate

        generate.write_bronze(generate.generate())
        gen = {"factories": s.n_factories, "months": s.n_months}
    else:
        from data_gen import engine

        gen = engine.build()
    t1 = time.perf_counter()
    from data_gen import lake
    from ml import features

    silver = lake.build_silver()
    t2 = time.perf_counter()
    gold = features.build_gold()
    t3 = time.perf_counter()
    stats = {"dataset": s.dataset, "generate": gen, "generate_seconds": round(t1 - t0, 1),
             "silver_seconds": round(t2 - t1, 1), "gold_seconds": round(t3 - t2, 1), "total_seconds": round(t3 - t0, 1),
             "silver_rows": int(len(silver)), "gold_rows": int(len(gold)), "gold_features": int(gold.shape[1] - 2),
             "peak_rss_mb_main": _mb(resource.RUSAGE_SELF), "peak_rss_mb_largest_worker": _mb(resource.RUSAGE_CHILDREN)}
    s.lake_dir.mkdir(parents=True, exist_ok=True)
    (s.lake_dir / "build_stats.json").write_text(json.dumps(stats, indent=2, default=str) + "\n")
    print(json.dumps({k: v for k, v in stats.items() if k != "generate"}))


if __name__ == "__main__":
    main()
