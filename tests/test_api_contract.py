"""API contract: versioning, problem+json errors, request ids and health probes."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import hero_app_id, login


@pytest.fixture(scope="module")
def root(client):
    """Same app, addressed from the root (health probes and unversioned paths)."""
    from api.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _assert_problem(r, status: int, code: str) -> dict:
    assert r.status_code == status
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == status and body["code"] == code and body["type"].endswith("/" + code)
    assert isinstance(body["detail"], str) and body["title"] and body["instance"].startswith("/")
    assert body["request_id"] == r.headers["x-request-id"]
    return body


def test_business_endpoints_exist_only_under_v1(client, root):
    assert root.get("/portfolio").status_code == 404
    assert root.get("/v1/portfolio").status_code == 401
    spec = root.get("/openapi.json").json()
    business = [p for p in spec["paths"] if p not in ("/healthz", "/readyz")]
    assert business and all(p.startswith("/v1/") for p in business)


def test_every_error_is_a_problem_document(client, root):
    rm = login(client, "rm1")
    _assert_problem(client.get("/portfolio"), 401, "unauthorized")
    _assert_problem(client.get("/audit", headers=rm), 403, "forbidden")
    _assert_problem(client.get("/applications/999999", headers=rm), 404, "not_found")
    _assert_problem(root.get("/v1/nope"), 404, "not_found")

    invalid = _assert_problem(client.post("/applications", headers=rm, json={}), 422, "validation_failed")
    assert invalid["errors"][0]["field"] == "factory_id"

    app_id = hero_app_id(client, rm)
    _assert_problem(client.post(f"/applications/{app_id}/score", headers=rm), 403, "consent_required")
    _assert_problem(client.post(f"/applications/{app_id}/memo", headers=rm), 409, "invalid_state")


def test_unhandled_errors_hide_internals(client, root, monkeypatch):
    from api.routers import portfolio

    def boom(*a, **k):
        raise RuntimeError("secret connection string")

    monkeypatch.setattr(portfolio, "get_lake", boom)
    rm = login(client, "rm1")
    body = _assert_problem(root.get("/v1/portfolio", headers=rm), 500, "internal_error")
    assert "secret" not in str(body)


def test_request_id_is_echoed_or_generated(root):
    assert root.get("/healthz", headers={"X-Request-ID": "demo-trace-0001"}).headers["x-request-id"] == "demo-trace-0001"
    generated = root.get("/healthz").headers["x-request-id"]
    assert len(generated) == 32
    # Unsafe values are replaced rather than reflected into logs and headers.
    assert root.get("/healthz", headers={"X-Request-ID": "x\r\ninjected: 1"}).headers["x-request-id"] != "x\r\ninjected: 1"


def test_liveness_and_readiness(root, monkeypatch):
    assert root.get("/healthz").json() == {"status": "ok"}
    ready = root.get("/readyz")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"
    assert set(ready.json()["checks"]) >= {"database", "model", "lake"}

    import api.main as main

    def down():
        raise ConnectionError("db down")

    monkeypatch.setattr(main, "_db", down)
    r = root.get("/readyz")
    database = r.json()["checks"]["database"]
    assert r.status_code == 503 and database["ok"] is False and database["error"] == "ConnectionError"
    assert root.get("/healthz").status_code == 200  # liveness does not depend on the database
