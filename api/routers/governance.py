from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from agents.providers.lake import get_lake
from api.auth import CurrentUser, require_roles
from api.models.db import AuditLog, get_db
from core.settings import get_settings

router = APIRouter(tags=["governance"])


@router.get("/audit")
def audit(application_id: int | None = None, limit: int = Query(default=200, le=2000), db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_roles("risk"))) -> list[dict]:
    q = db.query(AuditLog)
    if application_id is not None:
        q = q.filter(AuditLog.application_id == application_id)
    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()
    return [{"id": r.id, "ts": r.ts.isoformat(), "user": r.user, "role": r.role, "agent": r.agent, "tool": r.tool,
             "action": r.action, "application_id": r.application_id, "inputs": r.inputs,
             "output_hash": r.output_hash} for r in rows]


@router.get("/model")
def model_inventory(user: CurrentUser = Depends(require_roles("risk", "credit_officer", "rm"))) -> dict:
    """Model inventory entry: metrics, fairness, drift, EWS back-test and the model card."""
    s = get_settings()

    def load(name: str) -> dict | list | None:
        p = s.reports / name
        return json.loads(p.read_text()) if p.exists() else None

    card = s.ml_dir / "MODEL_CARD.md"
    return {
        "name": "udyampulse-pd", "type": "LightGBM binary classifier (12-month PD)", "owner": "risk-analytics",
        "metrics": load("metrics.json"), "fairness": load("fairness.json"), "drift": load("drift.json"),
        "ews_backtest": load("ews_backtest.json"), "model_card_md": card.read_text() if card.exists() else None,
    }


@router.get("/factories")
def factories(q: str = "", limit: int = Query(default=20, le=100),
              user: CurrentUser = Depends(require_roles("rm", "credit_officer", "risk"))) -> list[dict]:
    df = get_lake().profiles()
    if q:
        mask = df["name"].str.contains(q, case=False) | df["factory_id"].str.contains(q, case=False)
        df = df[mask]
    cols = ["factory_id", "name", "sector_label", "cluster", "udyam_category", "turnover_band", "loan_requested_inr"]
    return df[cols].head(limit).to_dict(orient="records")
