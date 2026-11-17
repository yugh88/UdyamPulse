"""Job status and live progress.

- `GET /v1/jobs/{id}`: one job (polling fallback).
- `GET /v1/jobs`: recent jobs for the caller's bank.
- `GET /v1/events`: Server-Sent Events. With `?job=<id>` the stream ends when that job finishes; without it,
  every job update in the caller's bank is streamed. The stream reads short-lived sessions, so no database
  connection is held open while a client is listening."""

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
from api.jobs import TERMINAL, job_view
from api.models.db import Job, SessionLocal, get_db, utcnow
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


def _poll(tenant: str, job_id: str | None, since) -> list[dict]:
    with SessionLocal() as db:
        bind_tenant(db, tenant)
        if job_id:
            job = db.get(Job, job_id)
            return [job_view(job)] if job else []
        rows = db.query(Job).filter(Job.updated_at >= since).order_by(Job.updated_at).limit(100).all()
        return [job_view(j) for j in rows]


@router.get("/events")
async def events(request: Request, job: str | None = None, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(get_current_user)) -> StreamingResponse:
    tenant = user.tenant_id
    db.close()  # authentication is done; release the connection for the life of the stream
    if job and not await run_in_threadpool(_poll, tenant, job, None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    async def stream():
        seen: dict[str, tuple] = {}
        since = utcnow() - timedelta(seconds=5)
        started = last_sent = time.monotonic()
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
            if job and rows and rows[0]["status"] in TERMINAL:
                return
            if time.monotonic() - last_sent > HEARTBEAT_SECONDS:
                last_sent = time.monotonic()
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
