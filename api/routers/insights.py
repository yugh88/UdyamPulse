"""Read-only decision support: policy clause lookup and the what-if score simulator."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.base import sim_date, visible_month
from agents.providers.consent import ConsentError, get_consent_provider
from agents.providers.lake import get_lake
from agents.providers.search import get_search
from api.auth import CurrentUser, require_roles
from api.models.db import Application, get_db
from api.models.schemas import SimulateRequest
from core.timeline import month_label
from ml.scoring import get_scorer
from ml.simulate import LEVER_BY_KEY, LEVERS, WINDOW_MONTHS, simulated_features

router = APIRouter(tags=["insights"])
STAFF = ("rm", "credit_officer", "risk")
SIMULATION_LABEL = "Simulation only · not a score of record · never used as a decision"


@router.get("/policy/{section}")
def policy_clause(section: str, user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    """Full text of one credit-policy clause, for the citation chips in the memo."""
    chunk = get_search().get(section)
    if chunk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Policy clause §{section} not found")
    return {"section": chunk.section, "title": chunk.title, "text": chunk.text,
            "source": "Sample MSME credit policy (policy/credit_policy.md)"}


@router.get("/score/levers")
def levers(user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    return {"window_months": WINDOW_MONTHS, "levers": [asdict(lv) for lv in LEVERS]}


@router.post("/score/simulate")
def simulate(body: SimulateRequest, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    """Re-score with a few signals changed over the latest months. Nothing is stored: the application's
    score, band and state are untouched and no data pull is recorded."""
    app = db.get(Application, body.application_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    unknown = sorted(set(body.adjustments) - set(LEVER_BY_KEY))
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown levers: {', '.join(unknown)}")
    if get_consent_provider(db).active(app.id, sim_date(db)) is None:
        raise ConsentError("No active consent: the simulator cannot read this factory's data")

    lake, scorer = get_lake(), get_scorer()
    month = visible_month(db)
    base_row = lake.features(app.factory_id, month)
    history = lake.history(app.factory_id, month)
    base = scorer.explain_row(base_row).to_dict()
    row = simulated_features(history, lake.profile(app.factory_id), base_row, body.adjustments)
    sim = scorer.explain_row(row).to_dict()
    applied = {k: max(LEVER_BY_KEY[k].min, min(LEVER_BY_KEY[k].max, v)) for k, v in body.adjustments.items()}
    return {
        "simulation": True, "label": SIMULATION_LABEL, "as_of": month_label(month), "window_months": WINDOW_MONTHS,
        "adjustments": applied,
        "base": {k: base[k] for k in ("score", "band", "pd_12m")},
        "simulated": {k: sim[k] for k in ("score", "band", "pd_12m", "reasons", "pillars")},
        "delta": sim["score"] - base["score"],
    }
