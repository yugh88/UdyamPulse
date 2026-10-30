"""Test fixtures. Builds the data/model pipeline once if artifacts are missing and uses a temporary DB."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="udyampulse-test-"))
os.environ["UP_DB_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["UP_LLM_PROVIDER"] = "template"

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
    with TestClient(app) as c:
        yield c


def login(client, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def hero_app_id(client, headers: dict) -> int:
    apps = client.get("/applications", headers=headers).json()
    return next(a["id"] for a in apps if a["factory_id"] == "UP-F0001")
