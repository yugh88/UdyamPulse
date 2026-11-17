"""Nightly early-warning and scoring batch over the whole lake, built to scale out.

    python -m ml.batch --month 24 --workers 4 --chunk-size 10000 [--shards 8]

- **Partitioning.** Accounts are assigned to a shard by `crc32(factory_id) % shards`, so one account always
  lands on the same shard, and shards split into chunks of `chunk_size` accounts.
- **Vectorised work.** Per chunk, DuckDB reads only that chunk's rows from Parquet, the EWS rules and the
  anomaly model run as column operations over every account at once, and the model scores the month's features
  in one call.
- **Parallelism.** `--workers N` runs chunks in N processes (the work is CPU-bound, so processes, not threads).
- **Checkpointing.** Each chunk writes its result atomically (temp file, then rename) and only then records
  itself in `batch_chunks`. Running the same command again resumes the unfinished run and skips finished chunks.
- **Stats.** Duration, accounts per second and per-worker throughput are stored on the run (`batch_runs.stats`)
  and shown on the System page.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
import zlib
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import duckdb
import joblib
import pandas as pd

from api.models.db import BatchChunk, BatchRun, SessionLocal, init_db, utcnow
from core.metrics import BATCH_ACCOUNTS
from core.settings import get_settings
from ml.ews import evaluate, rule_inputs

KIND = "ews.nightly"
HISTORY_MONTHS = 13  # rolling baselines look back up to 12 months


def shard_of(factory_id: str, shards: int) -> int:
    return zlib.crc32(factory_id.encode()) % shards


def plan_chunks(factory_ids: list[str], shards: int, chunk_size: int) -> list[tuple[int, list[str]]]:
    """[(shard, [factory ids])] in a stable order, so a resumed run produces the same chunk numbers."""
    by_shard: dict[int, list[str]] = {}
    for f in sorted(factory_ids):
        by_shard.setdefault(shard_of(f, shards), []).append(f)
    out = []
    for shard in sorted(by_shard):
        ids = by_shard[shard]
        out += [(shard, ids[i:i + chunk_size]) for i in range(0, len(ids), chunk_size)]
    return out


@lru_cache
def _anomaly_model():
    return joblib.load(get_settings().artifacts / "ews_iforest.joblib")


def _out_dir(run_id: str) -> Path:
    return get_settings().gold / "batch" / run_id


def process_chunk(run_id: str, chunk_no: int, factory_ids: list[str], month: int) -> dict:
    """Score and evaluate one chunk. Pure function of its inputs: safe to rerun after a crash."""
    from ml.scoring import get_scorer

    t0 = time.perf_counter()
    s = get_settings()
    con = duckdb.connect()
    con.register("ids", pd.DataFrame({"factory_id": factory_ids}))
    silver = con.execute(
        f"SELECT s.* FROM read_parquet('{(s.silver / 'factory_month.parquet').as_posix()}') s "
        "JOIN ids USING (factory_id) WHERE s.month BETWEEN ? AND ?", [month - HISTORY_MONTHS, month]).df()
    features = con.execute(
        f"SELECT g.* FROM read_parquet('{(s.gold / 'features.parquet').as_posix()}') g "
        "JOIN ids USING (factory_id) WHERE g.month = ?", [month]).df()
    con.close()

    inputs = rule_inputs(silver)
    hits = evaluate(inputs[inputs.month == month].reset_index(drop=True), _anomaly_model())
    scores = get_scorer().score_frame(features) if not features.empty else pd.DataFrame(
        columns=["factory_id", "month", "pd_12m", "score", "band"])
    out = scores.merge(hits[["factory_id", "month", "severity", "severity_points", "order_loss", "cash_squeeze",
                             "buyer_risk", "diversion", "compliance_slip", "anomaly"]],
                       on=["factory_id", "month"], how="outer")

    target = _out_dir(run_id)
    target.mkdir(parents=True, exist_ok=True)
    tmp = target / f".chunk_{chunk_no:05d}.{os.getpid()}.tmp"
    out.to_parquet(tmp, index=False)
    tmp.replace(target / f"chunk_{chunk_no:05d}.parquet")  # atomic: a crash never leaves a half-written chunk
    return {"chunk_no": chunk_no, "accounts": len(factory_ids),
            "alerts": int(out.severity.isin(["medium", "high"]).sum()),
            "seconds": round(time.perf_counter() - t0, 4), "worker": f"{os.environ.get('POD_NAME', 'worker')}-{os.getpid()}"}


def _accounts_for(month: int) -> list[str]:
    """Accounts that exist and have not defaulted by `month` (the population a bank would monitor)."""
    s = get_settings()
    labels = pd.read_parquet(s.gold / "labels.parquet", columns=["factory_id", "month", "is_post_default"])
    alive = labels[(labels.month == month) & (labels.is_post_default == 0)]
    return alive.factory_id.astype(str).tolist()


def run_batch(month: int, *, workers: int = 1, shards: int | None = None, chunk_size: int = 10_000,
              fail_on_chunk: int | None = None, on_chunk: Callable[[dict], None] | None = None) -> dict:
    """Run (or resume) the batch for `month`. Returns the run summary."""
    init_db()
    shards = shards or max(1, workers)
    accounts = _accounts_for(month)
    chunks = plan_chunks(accounts, shards, chunk_size)

    with SessionLocal() as db:
        run = (db.query(BatchRun).filter_by(kind=KIND, month=month, shards=shards, chunk_size=chunk_size,
                                            status="failed").order_by(BatchRun.started_at.desc()).first())
        if run is None:
            run = BatchRun(id=uuid.uuid4().hex, kind=KIND, month=month, shards=shards, chunk_size=chunk_size,
                           total_accounts=len(accounts), total_chunks=len(chunks))
            db.add(run)
        run.status, run.error, run.finished_at = "running", None, None
        db.commit()
        run_id = run.id
        done = {c.chunk_no for c in db.query(BatchChunk).filter_by(run_id=run_id)}

    todo = [(n, shard, ids) for n, (shard, ids) in enumerate(chunks) if n not in done]
    t0 = time.perf_counter()
    results: list[dict] = []

    def record(shard: int, r: dict) -> None:
        with SessionLocal() as db:
            db.add(BatchChunk(run_id=run_id, shard=shard, **r))
            db.commit()
        results.append(r)
        BATCH_ACCOUNTS.inc(r["accounts"])
        if on_chunk:
            on_chunk(r)

    try:
        if workers <= 1:
            for n, shard, ids in todo:
                if fail_on_chunk == n:
                    raise RuntimeError(f"simulated crash in chunk {n}")
                record(shard, process_chunk(run_id, n, ids, month))
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(process_chunk, run_id, n, ids, month): shard for n, shard, ids in todo}
                for fut in as_completed(futures):
                    record(futures[fut], fut.result())
    except BaseException as exc:
        with SessionLocal() as db:
            run = db.get(BatchRun, run_id)
            run.status, run.error, run.finished_at = "failed", f"{type(exc).__name__}: {exc}"[:500], utcnow()
            db.commit()
        raise

    wall = time.perf_counter() - t0
    with SessionLocal() as db:
        run = db.get(BatchRun, run_id)
        all_chunks = db.query(BatchChunk).filter_by(run_id=run_id).all()
        per_worker: dict[str, dict] = {}
        for c in all_chunks:
            w = per_worker.setdefault(c.worker, {"chunks": 0, "accounts": 0, "seconds": 0.0})
            w["chunks"] += 1
            w["accounts"] += c.accounts
            w["seconds"] = round(w["seconds"] + c.seconds, 4)
        processed = sum(r["accounts"] for r in results)
        run.status, run.finished_at = "succeeded", utcnow()
        run.stats = {
            "workers": workers, "processed_this_session": processed, "resumed_chunks": len(done),
            "wall_seconds": round(wall, 3),
            "accounts_per_second": round(processed / wall, 1) if wall and processed else None,
            "alerts_medium_or_high": sum(c.alerts for c in all_chunks),
            "per_worker": {k: {**v, "accounts_per_second": round(v["accounts"] / v["seconds"], 1) if v["seconds"] else None}
                           for k, v in per_worker.items()},
            "output": str(_out_dir(run_id).relative_to(get_settings().lake_dir)),
        }
        db.commit()
        return {"run_id": run_id, "status": run.status, "month": month, "accounts": run.total_accounts,
                "chunks": run.total_chunks, **run.stats}


def read_results(run_id: str) -> pd.DataFrame:
    return pd.read_parquet(_out_dir(run_id))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--month", type=int, default=get_settings().n_months)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--shards", type=int)
    p.add_argument("--chunk-size", type=int, default=10_000)
    a = p.parse_args()
    print(json.dumps(run_batch(a.month, workers=a.workers, shards=a.shards, chunk_size=a.chunk_size), indent=2))


if __name__ == "__main__":
    main()
