"""Test fixtures. Builds the data/model pipeline once if artifacts are missing and uses a temporary DB."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="udyampulse-test-"))
# SQLite by default; set UP_TEST_DB_URL to run the same suite against PostgreSQL (migrations + RLS).
os.environ["UP_DB_URL"] = os.environ.get("UP_TEST_DB_URL") or f"sqlite:///{_TMP / 'test.db'}"
os.environ["UP_LLM_PROVIDER"] = "template"
# Set UP_TEST_REDIS_URL to run against Redis (cache, limits, idempotency). The test database is flushed first.
if os.environ.get("UP_TEST_REDIS_URL"):
    os.environ["UP_REDIS_URL"] = os.environ["UP_TEST_REDIS_URL"]
    import redis as _redis

    _redis.Redis.from_url(os.environ["UP_REDIS_URL"]).flushdb()
    os.environ.setdefault("UP_INPROCESS_WORKER", "on")  # jobs run in the test process, through Redis
# Cheap argon2 for the hundreds of test logins (production cost is checked by the production guard).
os.environ.setdefault("UP_ARGON2_TIME_COST", "1")
os.environ.setdefault("UP_ARGON2_MEMORY_KIB", "1024")
os.environ.setdefault("UP_ARGON2_PARALLELISM", "1")
# Fast retries for the job tests.
os.environ.setdefault("UP_JOB_MIN_BACKOFF_MS", "50")
os.environ.setdefault("UP_JOB_MAX_BACKOFF_MS", "200")
# The suite logs in hundreds of times from one address; rate limits get their own tests.
for _k in ("UP_RATE_LIMIT_USER_PER_MIN", "UP_RATE_LIMIT_TENANT_PER_MIN", "UP_RATE_LIMIT_LOGIN_PER_MIN"):
    os.environ[_k] = "100000"

import pytest  # noqa: E402

from core.settings import get_settings  # noqa: E402


def _ensure_pipeline() -> None:
    s = get_settings()
    needed = [s.gold / "features.parquet", s.gold / "scores.parquet", s.gold / "ews_hits.parquet",
              s.artifacts / "model.txt"]
    if all(p.exists() for p in needed):
        return
    from data_gen import generate, lake
    from ml import ews, features, train

    generate.write_bronze(generate.generate())
    lake.build_silver()
    features.build_gold()
    train.main()
    ews.main()


@pytest.fixture(scope="session", autouse=True)
def pipeline() -> None:
    _ensure_pipeline()


@pytest.fixture(scope="module")
def client(pipeline):
    from fastapi.testclient import TestClient

    from api import seed
    from api.main import app

    seed.main()
    with TestClient(app, base_url="http://testserver/v1") as c:  # business endpoints are versioned
        yield c


def login(client, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def hero_app_id(client, headers: dict) -> int:
    apps = client.get("/applications", headers=headers).json()
    return next(a["id"] for a in apps if a["factory_id"] == "UP-F0001")


def wait_job(client, headers: dict, job_id: str, timeout: float = 30.0) -> dict:
    """Poll a background job until it reaches a terminal state."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/jobs/{job_id}", headers=headers).json()
        if job["terminal"]:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {job}")


def advance(client, headers: dict, days: int) -> dict:
    """Fast-forward the clock and wait for the early-warning batch; returns the batch result."""
    r = client.post(f"/sim/advance?days={days}", headers=headers)
    assert r.status_code == 202, r.text
    job = wait_job(client, headers, r.json()["job_id"])
    assert job["status"] == "succeeded", job
    return job["result"]
