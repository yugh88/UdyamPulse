"""Edge behaviour: rate limits, idempotency keys and the portfolio cache."""

from dataclasses import replace

import pytest

from api.kv import MemoryKV
from core.settings import get_settings
from tests.conftest import advance, hero_app_id, login


@pytest.fixture
def limits(monkeypatch):
    """Low limits and a fresh in-memory store for one test."""
    from api import middleware

    kv = MemoryKV()
    monkeypatch.setattr(middleware, "get_kv", lambda: kv)

    def apply(**kw):
        s = replace(get_settings(), **kw)
        monkeypatch.setattr(middleware, "get_settings", lambda: s)

    return apply


def test_user_rate_limit_returns_429_with_retry_after(client, limits):
    rm = login(client, "rm1")
    limits(rate_limit_user_per_min=5)
    codes = [client.get("/applications", headers=rm).status_code for _ in range(7)]
    assert codes == [200] * 5 + [429] * 2
    r = client.get("/applications", headers=rm)
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "rate_limited" and 1 <= int(r.headers["retry-after"]) <= 60
    # Another user of the same bank has a separate allowance; health probes are never limited.
    assert client.get("/applications", headers=login(client, "co1")).status_code == 200


def test_tenant_rate_limit_covers_all_users_of_a_bank(client, limits):
    rm, co, rm_b = login(client, "rm1"), login(client, "co1"), login(client, "rm2")
    limits(rate_limit_tenant_per_min=4)
    assert [client.get("/applications", headers=h).status_code for h in (rm, co, rm, co)] == [200] * 4
    assert client.get("/applications", headers=co).status_code == 429
    assert client.get("/applications", headers=rm_b).status_code == 200  # the other bank is unaffected


def test_login_attempts_are_limited_per_address(client, limits):
    limits(rate_limit_login_per_min=3)
    bad = {"username": "rm1", "password": "wrong"}
    assert [client.post("/auth/login", json=bad).status_code for _ in range(4)] == [401, 401, 401, 429]


def test_idempotency_key_replays_instead_of_repeating(client):
    rm = login(client, "rm1")
    factory = client.get("/factories?q=Ceramics&limit=1", headers=rm).json()[0]["factory_id"]
    headers = {**rm, "Idempotency-Key": "create-ceramics-0001"}
    first = client.post("/applications", headers=headers, json={"factory_id": factory})
    again = client.post("/applications", headers=headers, json={"factory_id": factory})
    assert first.status_code == again.status_code == 201
    assert again.json()["id"] == first.json()["id"] and again.headers["idempotency-replayed"] == "true"
    assert sum(a["factory_id"] == factory for a in client.get("/applications", headers=rm).json()) == 1

    reused = client.post("/applications", headers=headers, json={"factory_id": "UP-F0002"})
    assert reused.status_code == 422 and reused.json()["code"] == "idempotency_key_reused"
    # Keys are per user: the same key from someone else is a new request.
    other = client.post("/applications", headers={**login(client, "rm2"), "Idempotency-Key": "create-ceramics-0001"},
                        json={"factory_id": factory})
    assert other.status_code == 201 and other.json()["id"] != first.json()["id"]
    assert client.post("/applications", headers={**rm, "Idempotency-Key": "x" * 200},
                       json={"factory_id": factory}).status_code == 400


def test_idempotent_decision_is_recorded_once(client):
    rm, co = login(client, "rm1"), login(client, "co1")
    app_id = hero_app_id(client, rm)
    for step in ("consent", "score", "memo"):
        assert client.post(f"/applications/{app_id}/{step}", headers=rm).status_code == 200
    h = {**co, "Idempotency-Key": "decide-hero-0001"}
    body = {"decision": "APPROVED", "comment": "Approve per memo"}
    first = client.post(f"/applications/{app_id}/decision", headers=h, json=body)
    retry = client.post(f"/applications/{app_id}/decision", headers=h, json=body)
    assert first.status_code == retry.status_code == 200 and retry.json() == first.json()
    # Without the key, a second decision is a state error, which proves the retry was not re-executed.
    assert client.post(f"/applications/{app_id}/decision", headers=co, json=body).status_code == 409
    audit = client.get(f"/audit?application_id={app_id}&limit=2000", headers=login(client, "risk1")).json()
    assert sum(a["tool"] == "credit_decision" for a in audit) == 1


def test_portfolio_cache_hits_and_is_invalidated_by_writes(client):
    rm = login(client, "rm1")
    client.get("/portfolio", headers=rm)
    assert client.get("/portfolio", headers=rm).headers["x-cache"] == "hit"

    alert = client.get("/alerts", headers=rm).json()[0]
    assert client.post(f"/alerts/{alert['id']}/action", headers=rm, json={"action": "call"}).status_code == 200
    fresh = client.get("/portfolio", headers=rm)
    assert fresh.headers["x-cache"] == "miss", "a logged alert action must invalidate the cached aggregates"

    # A write in bank B leaves bank A's cache alone.
    client.get("/portfolio", headers=rm)
    rm_b = login(client, "rm2")
    alert_b = client.get("/alerts", headers=rm_b).json()
    if alert_b:
        client.post(f"/alerts/{alert_b[0]['id']}/action", headers=rm_b, json={"action": "call"})
    assert client.get("/portfolio", headers=rm).headers["x-cache"] == "hit"

    advance(client, rm, 7)  # the clock is global
    assert client.get("/portfolio", headers=rm).headers["x-cache"] == "miss"


def test_memory_kv_expiry_and_counters():
    import time

    kv = MemoryKV()
    assert kv.set_nx("a", "1", ttl=1) and not kv.set_nx("a", "2", ttl=1)
    assert kv.incr("n", ttl=1) == 1 and kv.incr("n", ttl=1) == 2
    kv.set("short", "x", ttl=0)
    time.sleep(0.01)
    assert kv.get("short") is None


def test_api_keeps_serving_when_redis_is_down(client, monkeypatch):
    """Redis is an accelerator, not a dependency of correctness: an outage degrades to no cache and no limits."""
    from api import cache, middleware
    from api.kv import RedisKV

    dead = RedisKV("redis://127.0.0.1:1/0")  # nothing listens on port 1
    monkeypatch.setattr(cache, "get_kv", lambda: dead)
    monkeypatch.setattr(middleware, "get_kv", lambda: dead)
    rm = login(client, "rm1")
    assert client.get("/portfolio", headers=rm).status_code == 200
    alert = client.get("/alerts", headers=rm).json()[0]
    r = client.post(f"/alerts/{alert['id']}/action", headers={**rm, "Idempotency-Key": "outage-0001"}, json={"action": "call"})
    assert r.status_code == 200
