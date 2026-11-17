from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from agents.providers.lake import get_lake
from agents.providers.llm import get_llm
from api.auth import CurrentUser, require_roles
from api.models.db import AiUsage, AuditLog, Consent, ConsentEvent, get_db
from core.settings import get_settings
from ml.features import FEATURES

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

    importance = load("feature_importance.json") or []
    for row in importance:
        row["pillar"] = FEATURES[row["feature"]].pillar if row["feature"] in FEATURES else None
    card = s.ml_dir / "MODEL_CARD.md"
    return {
        "name": "udyampulse-pd", "type": "LightGBM binary classifier (12-month PD)", "owner": "risk-analytics",
        "metrics": load("metrics.json"), "fairness": load("fairness.json"), "drift": load("drift.json"),
        "ews_backtest": load("ews_backtest.json"), "feature_importance": importance,
        "model_card_md": card.read_text() if card.exists() else None,
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


@router.get("/consent-ledger")
def consent_ledger(limit: int = Query(default=300, le=2000), db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_roles("risk"))) -> dict:
    """Portfolio-wide consent ledger: grants, data pulls, blocked pulls, expiries, revocations, deletion jobs."""
    lake = get_lake()
    counts = {st: db.query(Consent).filter_by(status=st).count() for st in ("ACTIVE", "REVOKED", "EXPIRED")}
    rows = db.query(ConsentEvent).order_by(ConsentEvent.id.desc()).limit(limit).all()
    return {
        "consents": counts,
        "events": [{"id": e.id, "ts": e.ts.isoformat(), "event": e.event, "consent_id": e.consent_id,
                    "factory_id": e.factory_id, "name": lake.profile(e.factory_id)["name"], "actor": e.actor,
                    "detail": e.detail} for e in rows],
    }


@router.get("/ai-usage")
def ai_usage(limit: int = Query(default=300, le=2000), db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_roles("risk"))) -> dict:
    """Every LLM-writer call: prompt template, provider, latency and a token estimate (characters / 4)."""
    rows = db.query(AiUsage).order_by(AiUsage.id.desc()).limit(limit).all()
    lat = sorted(r.latency_ms for r in rows)
    by_provider: dict[str, int] = {}
    for r in rows:
        by_provider[r.provider] = by_provider.get(r.provider, 0) + 1
    return {
        "summary": {
            "calls": len(rows), "by_provider": by_provider, "fallbacks": sum(1 for r in rows if r.fallback),
            "p50_latency_ms": lat[len(lat) // 2] if lat else None,
            "p95_latency_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
            "tokens_est": sum(r.tokens_est for r in rows),
            "provider_in_use": get_llm().name,
        },
        "calls": [{"id": r.id, "ts": r.ts.isoformat(), "agent": r.agent, "template_id": r.template_id,
                   "provider": r.provider, "location": "local" if r.provider == "template" else "cloud",
                   "latency_ms": r.latency_ms, "tokens_est": r.tokens_est, "fallback": r.fallback, "user": r.user,
                   "application_id": r.application_id} for r in rows],
    }


@router.post("/demo/reset", tags=["demo"])
def reset_demo() -> dict:
    """Presenter control: restore the seeded demo state. Available only in demo mode (local synthetic data)."""
    if not get_settings().demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    from api import seed
    from api.cache import invalidate_all

    t0 = time.perf_counter()
    seed.main()
    invalidate_all()
    return {"status": "reset", "took_ms": round((time.perf_counter() - t0) * 1000),
            "sim_date": str(get_settings().sim_start)}


@router.get("/demo/status", tags=["demo"])
def demo_status() -> dict:
    return {"demo_mode": get_settings().demo_mode}
