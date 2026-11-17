"""Operational view for staff: batch runs (and, in P6, live health and queue depth for the System page)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agents.base import visible_month
from api.auth import CurrentUser, require_roles
from api.jobs import enqueue
from api.models.db import BatchRun, get_db

router = APIRouter(prefix="/system", tags=["system"])
STAFF = ("rm", "credit_officer", "risk")


def _run(r: BatchRun) -> dict:
    return {"id": r.id, "kind": r.kind, "month": r.month, "status": r.status, "shards": r.shards,
            "chunk_size": r.chunk_size, "accounts": r.total_accounts, "chunks": r.total_chunks, "stats": r.stats,
            "error": r.error, "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None}


@router.get("/batch-runs")
def batch_runs(limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_roles(*STAFF))) -> list[dict]:
    return [_run(r) for r in db.query(BatchRun).order_by(BatchRun.started_at.desc()).limit(limit)]


@router.post("/batch-runs", status_code=202)
def start_batch(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("risk"))) -> dict:
    """Queue the nightly early-warning and scoring batch for the latest visible month."""
    job = enqueue(db, user, "batch.ews", {"month": visible_month(db)})
    db.commit()
    return {"job_id": job.id, "status": "queued", "status_url": f"/v1/jobs/{job.id}"}
