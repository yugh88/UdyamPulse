"""Job execution. One actor (`run_job`) loads the job and dispatches to a handler by kind.

Consumers are idempotent: a job is claimed with a conditional UPDATE (queued/retrying → running), so a
duplicate delivery of the same message finds nothing to claim and returns. A running job whose worker died
is reclaimed after its lease expires. Business-rule errors (no consent, wrong state) fail the job at once;
unexpected errors are retried with backoff and end in the dead-letter queue."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

import dramatiq
from dramatiq.middleware import CurrentMessage
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from agents.base import sim_date, visible_month
from agents.orchestrator import InvalidTransition, Orchestrator, ValidationFailed
from agents.providers.consent import ConsentError
from api.audit import Actor
from api.models.db import Application, Job, SessionLocal, utcnow
from api.tenancy import allow_cross_tenant, bind_tenant
from core.settings import get_settings
from core.timeline import month_label
from worker.broker import broker  # noqa: F401  (the broker must exist before actors are declared)

log = logging.getLogger("udyampulse.worker")
LEASE = timedelta(minutes=15)
BUSINESS_ERRORS = (ConsentError, InvalidTransition, ValidationFailed, LookupError)

Progress = Callable[[int, str], None]
Handler = Callable[[Session, Actor, Job, Progress], dict]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


def _application(db: Session, job: Job) -> Application:
    app = db.get(Application, job.application_id) if job.application_id else None
    if app is None:
        raise LookupError("Application not found")
    return app


@handler("ews.run")
def ews_run(db: Session, actor: Actor, job: Job, progress: Progress) -> dict:
    from agents.ews_agent import EarlyWarningAgent

    run = EarlyWarningAgent(db, actor).run(on_progress=lambda i, n: progress(int(i / n * 95), f"Checked {i} of {n} accounts"))
    return {**run.to_dict(), "sim_date": str(sim_date(db)), "data_month": month_label(visible_month(db))}


@handler("application.score")
def score_application(db: Session, actor: Actor, job: Job, progress: Progress) -> dict:
    progress(20, "Pulling consented data")
    result = Orchestrator(db, actor).score(_application(db, job))
    return {k: result[k] for k in ("score", "band", "pd_12m")}


@handler("application.memo")
def draft_memo(db: Session, actor: Actor, job: Job, progress: Progress) -> dict:
    progress(20, "Retrieving policy clauses and drafting")
    memo = Orchestrator(db, actor).draft_memo(_application(db, job))
    return {"generated_in_ms": memo["generated_in_ms"], "citations": len(memo["citations"]),
            "recommended_limit_display": memo["recommended_limit_display"]}


def _progress(db: Session, job_id: str) -> Progress:
    """Progress is written through the handler's own session, so one job holds one connection. Handlers call
    it only where everything before it may be committed: before work starts, or between accounts in the
    early-warning batch, which already commits account by account."""

    def update(pct: int, message: str) -> None:
        job = db.get(Job, job_id)
        job.progress, job.message, job.updated_at = max(0, min(99, pct)), message[:256], utcnow()
        db.commit()

    return update


def _retries_so_far() -> int:
    message = CurrentMessage.get_current_message()
    return message.options.get("retries", 0) if message else get_settings().job_max_retries


def execute(job_id: str) -> str:
    """Run one job. Returns the final status, or "skipped" for a duplicate or unknown delivery."""
    with SessionLocal() as db:
        allow_cross_tenant(db)  # the job id alone says which bank it belongs to
        found = db.get(Job, job_id)
        tenant = found.tenant_id if found else None
    if tenant is None:
        # The relay only publishes committed jobs, so a missing row means this worker is looking at the wrong
        # or a lagging database. Raise so the message is retried and finally dead-lettered, never silently lost.
        raise LookupError(f"job {job_id} not visible yet")

    with SessionLocal() as db:
        bind_tenant(db, tenant)
        now = utcnow()
        claimed = db.query(Job).filter(
            Job.id == job_id,
            or_(Job.status.in_(("queued", "retrying")), and_(Job.status == "running", Job.started_at < now - LEASE)),
        ).update({"status": "running", "attempts": Job.attempts + 1, "started_at": now, "message": "Running",
                  "error": None, "updated_at": now}, synchronize_session=False)
        db.commit()
        if not claimed:
            return "skipped"
        job = db.get(Job, job_id)
        fn = HANDLERS.get(job.kind)
        actor = Actor(job.created_by, job.role, None, tenant)
        try:
            if fn is None:
                raise LookupError(f"No handler for job kind '{job.kind}'")
            result = fn(db, actor, job, _progress(db, job_id))
            db.commit()
            job = db.get(Job, job_id)
            job.status, job.progress, job.message, job.result, job.finished_at = "succeeded", 100, "Done", result, utcnow()
            db.commit()
            return "succeeded"
        except BUSINESS_ERRORS as exc:
            db.rollback()
            job = db.get(Job, job_id)
            job.status, job.error, job.message, job.finished_at = "failed", str(exc)[:500], str(exc)[:256], utcnow()
            db.commit()
            return "failed"
        except Exception as exc:
            db.rollback()
            final = _retries_so_far() >= get_settings().job_max_retries
            job = db.get(Job, job_id)
            job.status = "dead" if final else "retrying"
            job.error = f"{type(exc).__name__}: {exc}"[:500]
            job.message = "Failed after all retries" if final else f"Attempt {job.attempts} failed; retrying"
            if final:
                job.finished_at = utcnow()
            db.commit()
            log.exception("job %s (%s) attempt %s failed", job_id, job.kind, job.attempts)
            raise  # Dramatiq retries with backoff, then dead-letters


@dramatiq.actor(queue_name="jobs")
def run_job(job_id: str) -> None:
    execute(job_id)


def execute_or_skip(job_id: str) -> str:
    """For direct calls (tests, tooling): a job that does not exist is reported, not raised."""
    try:
        return execute(job_id)
    except LookupError:
        return "skipped"
