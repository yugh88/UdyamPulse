from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.advisor_agent import AdvisorAgent
from agents.base import sim_date, visible_month
from agents.data_agent import DataAgent
from agents.memo_agent import AI_LABEL
from agents.providers.consent import ConsentError, get_consent_provider
from agents.providers.lake import get_lake
from api.audit import log_event
from api.auth import CurrentUser, ensure_factory_access, require_roles
from api.models.db import Application, ConsentEvent, DataSnapshot, Notification, get_db
from core.timeline import month_label
from ml.scoring import get_scorer

router = APIRouter(prefix="/msme", tags=["msme"])
ROLES = ("msme", "rm", "credit_officer")


def _latest_app(db: Session, factory_id: str) -> Application:
    app = db.query(Application).filter_by(factory_id=factory_id).order_by(Application.id.desc()).first()
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No application for this factory")
    return app


@router.get("/{factory_id}/readiness")
def readiness(factory_id: str, db: Session = Depends(get_db),
              user: CurrentUser = Depends(require_roles(*ROLES))) -> dict:
    ensure_factory_access(user, factory_id)
    lake = get_lake()
    app = _latest_app(db, factory_id)
    profile = lake.profile(factory_id)
    consent = get_consent_provider(db).active(app.id, sim_date(db))
    base = {"factory_id": factory_id, "name": profile["name"], "application_id": app.id, "state": app.state,
            "decision": app.decision, "review_requested": app.review_requested, "ai_label": AI_LABEL,
            "consent": {"active": consent is not None, **(consent.__dict__ if consent else {})}}
    try:
        pull = DataAgent(db, user).pull(app)
    except ConsentError:
        last = app.score_detail
        return {**base, "data_stale": True,
                "message": "Consent revoked: no new data is being pulled. Showing your last assessment only.",
                "score": last["score"] if last else None, "band": last["band"] if last else None,
                "plan": None}
    row = lake.features(factory_id, pull.upto_month)
    score = get_scorer().explain_row(row).to_dict()
    history = lake.history(factory_id, pull.upto_month)
    plan = AdvisorAgent(db, user).plan(score, history)
    return {**base, "data_stale": False, "data_month": month_label(pull.upto_month), "score": score["score"],
            "band": score["band"], "pillars": score["pillars"], "reasons": score["reasons"], "plan": plan}


@router.get("/{factory_id}/notifications")
def notifications(factory_id: str, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_roles(*ROLES))) -> list[dict]:
    ensure_factory_access(user, factory_id)
    rows = db.query(Notification).filter_by(factory_id=factory_id).order_by(Notification.id.desc()).limit(30).all()
    return [{"id": n.id, "channel": n.channel, "text": n.text, "sim_date": str(n.sim_date)} for n in rows]


@router.get("/{factory_id}/my-data")
def my_data(factory_id: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_roles(*ROLES))) -> dict:
    """DPDP data-principal rights stub: what is held, why, and the consent history."""
    ensure_factory_access(user, factory_id)
    snaps = db.query(DataSnapshot).filter_by(factory_id=factory_id).all()
    ledger = db.query(ConsentEvent).filter_by(factory_id=factory_id).order_by(ConsentEvent.id).all()
    return {
        "purpose": "Working-capital underwriting and loan monitoring",
        "data_categories": ["GST returns & e-invoices", "E-way bills", "Bank statements (Account Aggregator)",
                            "Electricity consumption", "ERP stock/orders", "EPFO headcount"],
        "not_collected": ["Biometrics", "Personal contacts", "Location history"],
        "snapshots_held": len(snaps),
        "retention": "Deleted on consent revocation, or 8 years after loan closure where required by law",
        "consent_ledger": [{"ts": e.ts.isoformat(), "event": e.event, "actor": e.actor} for e in ledger],
        "data_visible_through": month_label(visible_month(db)),
    }


@router.post("/{factory_id}/erasure-request")
def erasure_request(factory_id: str, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_roles("msme"))) -> dict:
    ensure_factory_access(user, factory_id)
    log_event(db, user, agent="api", tool="dpdp_rights", action="erasure_request", inputs={"factory_id": factory_id})
    return {"status": "Erasure request logged; the lender's grievance officer will respond within 30 days"}
