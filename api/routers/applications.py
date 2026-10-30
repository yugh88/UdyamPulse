from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from agents.base import sim_date, visible_month
from agents.memo_agent import AI_LABEL
from agents.orchestrator import Orchestrator
from agents.providers.consent import get_consent_provider
from agents.providers.lake import get_lake
from api.audit import log_event
from api.auth import CurrentUser, ensure_factory_access, get_current_user, require_roles
from api.models.db import Alert, Application, ConsentEvent, get_db
from api.models.schemas import ApplicationCreate, DecisionRequest, ReviewRequest, ScoreResponse
from core.settings import get_settings
from core.timeline import month_label

router = APIRouter(prefix="/applications", tags=["applications"])
STAFF = ("rm", "credit_officer", "risk")


def _get_app(db: Session, app_id: int, user: CurrentUser) -> Application:
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    ensure_factory_access(user, app.factory_id)
    return app


def _summary(app: Application, profile: dict) -> dict:
    return {
        "id": app.id, "factory_id": app.factory_id, "name": profile["name"], "sector": profile["sector_label"],
        "cluster": profile["cluster"], "udyam_category": profile["udyam_category"], "state": app.state,
        "requested_amount": app.requested_amount, "score": app.score, "band": app.band, "decision": app.decision,
        "channel": app.channel, "created_at": app.created_at.isoformat() if app.created_at else None,
        "review_requested": app.review_requested,
    }


@router.get("")
def list_applications(state: str | None = None, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require_roles(*STAFF))) -> list[dict]:
    lake = get_lake()
    q = db.query(Application)
    if state:
        q = q.filter(Application.state == state)
    else:
        q = q.filter(Application.state != "MONITORING")
    return [_summary(a, lake.profile(a.factory_id)) for a in q.order_by(Application.id).all()]


@router.post("", status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require_roles("rm", "msme"))) -> dict:
    ensure_factory_access(user, body.factory_id)
    try:
        app = Orchestrator(db, user).create(body.factory_id, body.requested_amount, body.channel)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown factory {body.factory_id}") from exc
    return _summary(app, get_lake().profile(app.factory_id))


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)) -> dict:
    app = _get_app(db, app_id, user)
    lake = get_lake()
    profile = lake.profile(app.factory_id)
    consent = get_consent_provider(db).active(app.id, sim_date(db))
    signals = []
    if consent:  # signals are only shown while consent is active
        hist = lake.history(app.factory_id, visible_month(db))
        signals = [{"month": month_label(int(r.month)), "eway_value": round(r.eway_value),
                    "kwh": round(r.kwh), "aa_credits": round(r.aa_credits)} for r in hist.itertuples()]
    alerts = db.query(Alert).filter_by(application_id=app.id).order_by(Alert.month.desc()).all()
    return {
        **_summary(app, profile),
        "profile": {k: profile[k] for k in ("vintage_years", "turnover_band", "annual_turnover_cr", "n_buyers",
                                            "udyam_number")},
        "consent": {"active": consent is not None, **(consent.__dict__ if consent else {})},
        "data_checks": app.data_checks,
        "score_detail": app.score_detail,
        "memo": {k: v for k, v in (app.memo or {}).items() if k != "facts"} or None,
        "memo_pdf_url": f"/applications/{app.id}/memo.pdf" if app.memo_pdf else None,
        "pricing_band": app.pricing_band, "recommended_limit": app.recommended_limit,
        "decision_comment": app.decision_comment, "decided_by": app.decided_by, "kfs": app.kfs,
        "sanctioned_limit": app.sanctioned_limit, "disbursement_ref": app.disbursement_ref,
        "disbursed_on": str(app.disbursed_on) if app.disbursed_on else None,
        "signals": signals,
        "alerts": [{"id": a.id, "month": month_label(a.month), "severity": a.severity, "status": a.status,
                    "next_best_action": a.next_best_action} for a in alerts],
        "ai_label": AI_LABEL,
    }


@router.post("/{app_id}/consent")
def grant_consent(app_id: int, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_roles("rm", "msme"))) -> dict:
    return Orchestrator(db, user).consent(_get_app(db, app_id, user))


@router.delete("/{app_id}/consent")
def revoke_consent(app_id: int, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_roles("rm", "msme"))) -> dict:
    return Orchestrator(db, user).revoke(_get_app(db, app_id, user))


@router.get("/{app_id}/consent-ledger")
def consent_ledger(app_id: int, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    app = _get_app(db, app_id, user)
    rows = db.query(ConsentEvent).filter_by(factory_id=app.factory_id).order_by(ConsentEvent.id).all()
    return [{"ts": r.ts.isoformat(), "event": r.event, "consent_id": r.consent_id, "actor": r.actor,
             "detail": r.detail} for r in rows]


@router.post("/{app_id}/score", response_model=ScoreResponse)
def score_application(app_id: int, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require_roles("rm", "credit_officer"))) -> dict:
    result = Orchestrator(db, user).score(_get_app(db, app_id, user))
    return {**result, "ai_label": AI_LABEL}


@router.post("/{app_id}/memo")
def draft_memo(app_id: int, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_roles("rm", "credit_officer"))) -> dict:
    memo = Orchestrator(db, user).draft_memo(_get_app(db, app_id, user))
    return {**{k: v for k, v in memo.items() if k != "facts"}, "pdf_url": f"/applications/{app_id}/memo.pdf"}


@router.get("/{app_id}/memo.pdf")
def memo_pdf(app_id: int, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_roles(*STAFF))) -> FileResponse:
    app = _get_app(db, app_id, user)
    if not app.memo_pdf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not generated yet")
    return FileResponse(get_settings().var_dir / app.memo_pdf, media_type="application/pdf",
                        filename=f"credit_memo_{app_id}.pdf", content_disposition_type="inline")


@router.post("/{app_id}/decision")
def decide(app_id: int, body: DecisionRequest, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_roles("credit_officer"))) -> dict:
    return Orchestrator(db, user).decide(_get_app(db, app_id, user), body.decision, body.comment,
                                         body.sanctioned_limit)


@router.post("/{app_id}/disburse")
def disburse(app_id: int, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_roles("credit_officer", "rm"))) -> dict:
    return Orchestrator(db, user).disburse(_get_app(db, app_id, user))


@router.post("/{app_id}/review-request")
def request_review(app_id: int, body: ReviewRequest, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(get_current_user)) -> dict:
    """Right to challenge an AI-assisted outcome (RBI FREE-AI): routes the case to a human reviewer."""
    app = _get_app(db, app_id, user)
    app.review_requested, app.review_note = True, body.note
    log_event(db, user, agent="api", tool="review_request", action="request_review", inputs={"note": body.note},
              application_id=app.id)
    return {"status": "Review requested — a credit officer will respond", "application_id": app.id}
