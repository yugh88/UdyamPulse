"""Job status and live progress.

- `GET /v1/jobs/{id}`: one job (polling fallback).
- `GET /v1/jobs`: recent jobs for the caller's bank.
- `GET /v1/events`: Server-Sent Events. With `?job=<id>` the stream ends when that job finishes; without it,
  every job update in the caller's bank is streamed. With `?changes=1` it also streams change events
  (`event: change`: score, alert, state, decision, consent) within the caller's branch or factory scope, for
  live toasts and cache refreshes. The stream reads short-lived sessions, so no database connection is held
  open while a client is listening."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.auth import CurrentUser, get_current_user
from api.authz import branch_clusters
from api.jobs import TERMINAL, job_view
from api.models.db import Application, ChangeEvent, Job, SessionLocal, get_db, utcnow
from api.tenancy import bind_tenant

router = APIRouter(tags=["jobs"])
POLL_SECONDS = 0.4
HEARTBEAT_SECONDS = 15
MAX_STREAM_SECONDS = 15 * 60


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job_view(job)


@router.get("/jobs")
def list_jobs(limit: int = Query(default=20, le=100), db: Session = Depends(get_db),
              user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return [job_view(j) for j in db.query(Job).order_by(Job.created_at.desc()).limit(limit)]


def _poll_changes(user: CurrentUser, after_id: int | None) -> tuple[int, list[dict]]:
    """Change events after `after_id` that this user may see. The first call only returns the high-water mark."""
    from sqlalchemy import func, select

    with SessionLocal() as db:
        bind_tenant(db, user.tenant_id)
        if after_id is None:
            return db.query(func.coalesce(func.max(ChangeEvent.id), 0)).scalar(), []
        q = db.query(ChangeEvent).filter(ChangeEvent.id > after_id)
        if user.role == "msme":
            q = q.filter(ChangeEvent.application_id.in_(
                select(Application.id).where(Application.factory_id == user.factory_id)))
        elif (clusters := branch_clusters(user)) is not None:
            q = q.filter(ChangeEvent.application_id.in_(
                select(Application.id).where(Application.cluster.in_(clusters))))
        rows = q.order_by(ChangeEvent.id).limit(100).all()
        out = [{"id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
                "application_id": r.application_id, "event_type": r.event_type, "summary": r.summary,
                "before": r.before, "after": r.after, "actor": r.actor, "created_at": r.created_at.isoformat()}
               for r in rows]
        return (rows[-1].id if rows else after_id), out


def _poll(tenant: str, job_id: str | None, since) -> list[dict]:
    with SessionLocal() as db:
        bind_tenant(db, tenant)
        if job_id:
            job = db.get(Job, job_id)
            return [job_view(job)] if job else []
        rows = db.query(Job).filter(Job.updated_at >= since).order_by(Job.updated_at).limit(100).all()
        return [job_view(j) for j in rows]


@router.get("/events")
async def events(request: Request, job: str | None = None, changes: bool = False, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(get_current_user)) -> StreamingResponse:
    tenant = user.tenant_id
    db.close()  # authentication is done; release the connection for the life of the stream
    if job and not await run_in_threadpool(_poll, tenant, job, None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    async def stream():
        seen: dict[str, tuple] = {}
        since = utcnow() - timedelta(seconds=5)
        started = last_sent = time.monotonic()
        change_mark = (await run_in_threadpool(_poll_changes, user, None))[0] if changes else None
        yield "retry: 2000\n\n"
        while time.monotonic() - started < MAX_STREAM_SECONDS:
            if await request.is_disconnected():
                return
            rows = await run_in_threadpool(_poll, tenant, job, since)
            for r in rows:
                key = (r["status"], r["progress"], r["message"])
                if seen.get(r["id"]) != key:
                    seen[r["id"]] = key
                    last_sent = time.monotonic()
                    yield f"id: {r['id']}-{r['updated_at']}\nevent: job\ndata: {json.dumps(r, default=str)}\n\n"
            if changes:
                change_mark, fresh = await run_in_threadpool(_poll_changes, user, change_mark)
                for c in fresh:
                    last_sent = time.monotonic()
                    yield f"id: change-{c['id']}\nevent: change\ndata: {json.dumps(c, default=str)}\n\n"
            if job and rows and rows[0]["status"] in TERMINAL:
                return
            if time.monotonic() - last_sent > HEARTBEAT_SECONDS:
                last_sent = time.monotonic()
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
