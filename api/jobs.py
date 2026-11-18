"""Enqueueing background jobs and domain events through the transactional outbox.

`enqueue` and `emit` only add rows to the caller's session. The job row, its `job.requested` outbox event
and the business change commit together; the relay then hands the job to the queue. If the transaction
rolls back, nothing is queued; if the process dies after the commit, the relay still finds the event."""

from __future__ import annotations

import threading
import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session

from api.audit import Actor
from api.models.db import Job, OutboxEvent
from core.telemetry import carrier

TERMINAL = frozenset({"succeeded", "failed", "dead"})
RELAY_WAKE = threading.Event()  # lets an in-process relay publish right after a commit instead of on its next poll
_OUTBOX_TOUCHED = "outbox_touched"


def enqueue(db: Session, actor: Actor, kind: str, params: dict | None = None, *, application_id: int | None = None) -> Job:
    params = {**(params or {})}
    trace_ctx = carrier()
    if trace_ctx:
        params["_trace"] = trace_ctx  # the worker continues this request's trace
    job = Job(id=uuid.uuid4().hex, kind=kind, params=params, status="queued", progress=0, message="Queued",
              attempts=0, created_by=actor.username, role=actor.role, application_id=application_id)
    db.add(job)
    db.add(OutboxEvent(topic="job.requested", payload={"job_id": job.id, "kind": kind}))
    return job


def emit(db: Session, topic: str, payload: dict) -> None:
    """Domain event (alert raised, decision made, consent revoked) for downstream consumers."""
    db.add(OutboxEvent(topic=topic, payload=payload))


def job_view(job: Job) -> dict:
    return {
        "id": job.id, "kind": job.kind, "status": job.status, "progress": job.progress, "message": job.message,
        "result": job.result, "error": job.error, "attempts": job.attempts, "application_id": job.application_id,
        "created_by": job.created_by, "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "terminal": job.status in TERMINAL,
    }


@event.listens_for(Session, "before_flush")
def _track(session: Session, _ctx, _instances) -> None:
    if any(isinstance(o, OutboxEvent) for o in session.new):
        session.info[_OUTBOX_TOUCHED] = True


@event.listens_for(Session, "after_commit")
def _wake(session: Session) -> None:
    if session.info.pop(_OUTBOX_TOUCHED, False):
        RELAY_WAKE.set()
