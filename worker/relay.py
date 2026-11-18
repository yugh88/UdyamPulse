"""Outbox relay: publishes committed outbox events.

- `job.requested` → enqueue `run_job` on the Dramatiq broker.
- any other topic (domain events) → the event stream (`udyampulse:events` Redis stream, or an in-memory
  ring for the lite demo; Azure Event Hubs in production).

Delivery is at least once: if the process dies between publishing and marking the row, the event is sent
again and the idempotent consumer ignores the duplicate. Several relays can run side by side on PostgreSQL
(`FOR UPDATE SKIP LOCKED`)."""

from __future__ import annotations

import collections
import json
import logging
import threading

from api.jobs import RELAY_WAKE
from api.models.db import OutboxEvent, SessionLocal, utcnow
from api.tenancy import allow_cross_tenant
from core.settings import get_settings

log = logging.getLogger("udyampulse.relay")
RECENT_EVENTS: collections.deque = collections.deque(maxlen=500)  # lite-demo event stream
STREAM = "udyampulse:events"


def _publish(event: OutboxEvent) -> None:
    if event.topic == "job.requested":
        from worker.tasks import run_job

        run_job.send(event.payload["job_id"])
        return
    record = {"id": event.id, "tenant_id": event.tenant_id, "topic": event.topic, "payload": event.payload,
              "created_at": event.created_at.isoformat() if event.created_at else None}
    url = get_settings().redis_url
    if url:
        import redis

        redis.Redis.from_url(url).xadd(STREAM, {"event": json.dumps(record, default=str)}, maxlen=100_000, approximate=True)
    else:
        RECENT_EVENTS.append(record)


def recent_events(limit: int = 100) -> list[dict]:
    """Newest-last domain events from whichever stream is in use."""
    url = get_settings().redis_url
    if not url:
        return list(RECENT_EVENTS)[-limit:]
    import redis

    rows = redis.Redis.from_url(url).xrevrange(STREAM, count=limit)
    return [json.loads(fields[b"event"]) for _id, fields in reversed(rows)]


def publish_pending(limit: int = 200) -> int:
    with SessionLocal() as db:
        allow_cross_tenant(db)
        q = db.query(OutboxEvent).filter(OutboxEvent.published_at.is_(None)).order_by(OutboxEvent.id).limit(limit)
        if db.get_bind().dialect.name == "postgresql":
            q = q.with_for_update(skip_locked=True)
        events = q.all()
        for e in events:
            try:
                _publish(e)
                e.published_at = utcnow()
            except Exception as exc:  # stays unpublished and is retried on the next pass
                e.attempts += 1
                e.last_error = f"{type(exc).__name__}: {exc}"[:500]
                log.warning("outbox event %s (%s) not published: %s", e.id, e.topic, exc)
        db.commit()
        return len(events)


def run_relay(stop: threading.Event, idle_wait: float = 0.5) -> None:
    while not stop.is_set():
        try:
            published = publish_pending()
        except Exception:
            log.exception("outbox relay pass failed")
            published = 0
        if not published:
            RELAY_WAKE.wait(idle_wait)
            RELAY_WAKE.clear()
