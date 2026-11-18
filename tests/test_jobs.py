"""Background jobs: outbox → relay → Dramatiq → idempotent consumer, with retries, dead letters and SSE."""

import json
import time

import pytest

from api.audit import Actor
from api.jobs import enqueue, job_view
from api.models.db import Job, OutboxEvent, SessionLocal
from api.tenancy import allow_cross_tenant, bind_tenant
from tests.conftest import hero_app_id, hero_score, login, wait_job
from worker import tasks
from worker.broker import broker

ASYNC = {"Prefer": "respond-async"}
RM_A = Actor("rm1", "rm", None, "bank-a")


def _enqueue(kind: str, params: dict | None = None) -> str:
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        job = enqueue(db, RM_A, kind, params)
        db.commit()
        return job.id


def _wait(job_id: str, timeout: float = 20) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            allow_cross_tenant(db)
            view = job_view(db.get(Job, job_id))
        if view["terminal"]:
            return view
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} still {view['status']}")


@pytest.fixture
def handlers():
    added: list[str] = []

    def register(kind, fn):
        tasks.HANDLERS[kind] = fn
        added.append(kind)

    yield register
    for k in added:
        tasks.HANDLERS.pop(k, None)


def test_async_scoring_returns_202_and_streams_progress(client):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    r = client.post(f"/applications/{app_id}/score", headers={**rm, **ASYNC})
    assert r.status_code == 202 and r.headers["location"] == f"/v1/jobs/{r.json()['job_id']}"
    assert r.headers["preference-applied"] == "respond-async"

    events = []
    with client.stream("GET", f"/events?job={r.json()['job_id']}", headers=rm) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    assert events[-1]["status"] == "succeeded" and events[-1]["result"]["score"] == hero_score()
    assert [e["status"] for e in events][-1] == "succeeded" and len(events) >= 1
    assert client.get(f"/applications/{app_id}", headers=rm).json()["state"] == "SCORED"

    memo = client.post(f"/applications/{app_id}/memo", headers={**rm, **ASYNC})
    done = wait_job(client, rm, memo.json()["job_id"])
    assert done["status"] == "succeeded" and done["result"]["citations"] >= 2


def test_business_errors_fail_once_without_retry(client):
    rm = login(client, "rm1")
    other = next(a["id"] for a in client.get("/applications", headers=rm).json()
                 if a["factory_id"] != "UP-F0001" and a["state"] == "APPLIED")
    r = client.post(f"/applications/{other}/score", headers={**rm, **ASYNC})  # no consent yet
    job = wait_job(client, rm, r.json()["job_id"])
    assert job["status"] == "failed" and job["attempts"] == 1 and "consent" in job["error"].lower()


def test_transient_errors_are_retried_with_backoff(client, handlers):
    calls = []

    def flaky(db, actor, job, progress):
        calls.append(time.monotonic())
        if len(calls) < 3:
            raise ConnectionError("upstream timeout")
        return {"ok": True}

    handlers("test.flaky", flaky)
    job = _wait(_enqueue("test.flaky"))
    assert job["status"] == "succeeded" and job["attempts"] == 3 and job["result"] == {"ok": True}
    assert calls[1] - calls[0] >= 0.04 and calls[2] - calls[1] >= 0.04  # backoff between attempts


def test_exhausted_retries_end_in_the_dead_letter_queue(client, handlers):
    from core.settings import get_settings

    handlers("test.broken", lambda *a: (_ for _ in ()).throw(RuntimeError("always broken")))
    job = _wait(_enqueue("test.broken"))
    assert job["status"] == "dead" and job["attempts"] == get_settings().job_max_retries + 1
    assert "RuntimeError: always broken" in job["error"]
    deadline = time.monotonic() + 5
    while not _dead_lettered(job["id"]) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _dead_lettered(job["id"])


def _dead_lettered(job_id: str) -> bool:
    if hasattr(broker, "dead_letters"):  # in-process stub broker
        return any(m.args == (job_id,) for m in broker.dead_letters)
    stored = broker.client.hvals("udyampulse:jobs.XQ.msgs")  # Redis dead-letter queue
    return any(job_id.encode() in raw for raw in stored)


def test_duplicate_delivery_runs_the_handler_once(client, handlers):
    runs = []
    handlers("test.count", lambda db, actor, job, progress: runs.append(job.id) or {"n": len(runs)})
    job_id = _enqueue("test.count")
    assert _wait(job_id)["status"] == "succeeded"
    assert tasks.execute(job_id) == "skipped" and tasks.execute(job_id) == "skipped"  # redelivered twice
    assert runs == [job_id]
    assert tasks.execute_or_skip("does-not-exist") == "skipped"
    with pytest.raises(LookupError):  # through the queue, a missing row is retried rather than acknowledged
        tasks.execute("does-not-exist")


def test_rolled_back_work_queues_nothing(client):
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        jobs, events = db.query(Job).count(), db.query(OutboxEvent).count()
        enqueue(db, RM_A, "ews.run")
        db.flush()
        db.rollback()
        assert db.query(Job).count() == jobs and db.query(OutboxEvent).count() == events


def test_domain_events_are_published_through_the_outbox(client):
    from worker.relay import recent_events

    rm, co = login(client, "rm1"), login(client, "co1")
    app_id = hero_app_id(client, rm)
    for step in ("consent", "score", "memo"):
        client.post(f"/applications/{app_id}/{step}", headers=rm)
    client.post(f"/applications/{app_id}/decision", headers=co, json={"decision": "APPROVED", "comment": "Approve"})
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        decided = [e for e in recent_events(500) if e["topic"] == "application.decided" and e["payload"]["application_id"] == app_id]
        if decided:
            break
        time.sleep(0.05)
    assert decided and decided[-1]["tenant_id"] == "bank-a" and decided[-1]["payload"]["decision"] == "APPROVED"
    with SessionLocal() as db:
        allow_cross_tenant(db)
        row = db.get(OutboxEvent, decided[-1]["id"])
        assert row.published_at is not None


def test_failed_publish_stays_in_the_outbox_until_it_succeeds(client, monkeypatch):
    from worker import relay

    real = relay._publish
    monkeypatch.setattr(relay, "_publish", lambda e: (_ for _ in ()).throw(ConnectionError("broker down")))
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        event = OutboxEvent(topic="test.event", payload={"n": 1})
        db.add(event)
        db.flush()
        event_id = event.id
        db.commit()
    relay.publish_pending()
    with SessionLocal() as db:
        allow_cross_tenant(db)
        row = db.get(OutboxEvent, event_id)
        assert row.published_at is None and row.attempts >= 1 and "broker down" in row.last_error
    monkeypatch.setattr(relay, "_publish", real)
    relay.publish_pending()
    with SessionLocal() as db:
        allow_cross_tenant(db)
        assert db.get(OutboxEvent, event_id).published_at is not None


def test_jobs_are_tenant_scoped(client):
    rm_a, rm_b = login(client, "rm1"), login(client, "rm2")
    job_id = client.post("/sim/advance?days=1", headers=rm_a).json()["job_id"]
    assert client.get(f"/jobs/{job_id}", headers=rm_a).status_code == 200
    assert client.get(f"/jobs/{job_id}", headers=rm_b).status_code == 404
    assert client.get(f"/events?job={job_id}", headers=rm_b).status_code == 404
    assert job_id not in {j["id"] for j in client.get("/jobs", headers=rm_b).json()}
    wait_job(client, rm_a, job_id)
