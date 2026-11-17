"""Chunked nightly batch: same answers as the pipeline, resumes after a crash, runs across processes."""

import pandas as pd
import pytest

from api.models.db import BatchChunk, BatchRun, SessionLocal
from core.settings import get_settings
from ml.batch import plan_chunks, read_results, run_batch, shard_of

MONTH = 20


def test_sharding_is_stable_and_complete():
    ids = [f"UP-F{i:04d}" for i in range(1, 501)]
    chunks = plan_chunks(ids, shards=4, chunk_size=60)
    flat = [f for _, c in chunks for f in c]
    assert sorted(flat) == ids and len(flat) == len(set(flat))
    assert all(len(c) <= 60 for _, c in chunks)
    assert all(shard_of(f, 4) == shard for shard, c in chunks for f in c)
    assert plan_chunks(list(reversed(ids)), 4, 60) == chunks  # input order does not change the plan


def test_batch_matches_the_pipeline(client):
    summary = run_batch(MONTH, chunk_size=70)
    assert summary["status"] == "succeeded" and summary["chunks"] == -(-summary["accounts"] // 70)
    out = read_results(summary["run_id"])
    assert len(out) == summary["accounts"] and out.factory_id.is_unique

    s = get_settings()
    ref_hits = pd.read_parquet(s.gold / "ews_hits.parquet")
    ref_hits = ref_hits[ref_hits.month == MONTH].set_index("factory_id")
    ref_scores = pd.read_parquet(s.gold / "scores.parquet")
    ref_scores = ref_scores[ref_scores.month == MONTH].set_index("factory_id")
    got = out.set_index("factory_id")
    common = got.index.intersection(ref_hits.index)
    assert len(common) == len(got)
    assert (got.loc[common, "severity"].fillna("") == ref_hits.loc[common, "severity"].fillna("")).all()
    assert (got.loc[common, "score"] == ref_scores.loc[common, "score"]).all()


def test_a_crashed_run_resumes_without_redoing_finished_chunks(client):
    with pytest.raises(RuntimeError, match="simulated crash"):
        run_batch(MONTH - 1, chunk_size=50, fail_on_chunk=4)
    with SessionLocal() as db:
        run = db.query(BatchRun).filter_by(month=MONTH - 1).one()
        assert run.status == "failed" and "simulated crash" in run.error
        assert db.query(BatchChunk).filter_by(run_id=run.id).count() == 4

    redone = []
    summary = run_batch(MONTH - 1, chunk_size=50, on_chunk=lambda r: redone.append(r["chunk_no"]))
    assert summary["run_id"] == run.id and summary["status"] == "succeeded"
    assert summary["resumed_chunks"] == 4 and min(redone) == 4  # chunks 0-3 were not recomputed
    assert len(read_results(run.id)) == summary["accounts"]


def test_parallel_workers_produce_the_same_result(client):
    one = read_results(run_batch(MONTH - 2, chunk_size=80, workers=1)["run_id"]).sort_values("factory_id")
    summary = run_batch(MONTH - 2, chunk_size=80, workers=2, shards=2)
    two = read_results(summary["run_id"]).sort_values("factory_id")
    assert len(summary["per_worker"]) >= 2 and summary["accounts_per_second"] > 0
    pd.testing.assert_frame_equal(one.reset_index(drop=True)[["factory_id", "score", "severity"]],
                                  two.reset_index(drop=True)[["factory_id", "score", "severity"]])


def test_risk_can_run_the_batch_as_a_job_and_staff_can_see_runs(client):
    from tests.conftest import login, wait_job

    risk, rm = login(client, "risk1"), login(client, "rm1")
    assert client.post("/system/batch-runs", headers=rm).status_code == 403
    job = wait_job(client, risk, client.post("/system/batch-runs", headers=risk).json()["job_id"])
    assert job["status"] == "succeeded" and job["result"]["accounts"] > 0
    runs = client.get("/system/batch-runs", headers=rm).json()
    assert runs[0]["id"] == job["result"]["run_id"] and runs[0]["stats"]["accounts_per_second"] > 0
