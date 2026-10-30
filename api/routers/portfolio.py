from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from agents.base import set_sim_date, sim_date, visible_month
from agents.ews_agent import EarlyWarningAgent
from agents.memo_agent import AI_LABEL
from agents.providers.consent import get_consent_provider
from agents.providers.lake import get_lake
from api.audit import log_event
from api.auth import CurrentUser, require_roles
from api.models.db import Alert, Application, get_db
from api.models.schemas import AlertAction
from core.timeline import month_label

router = APIRouter(tags=["portfolio"])
STAFF = ("rm", "credit_officer", "risk")
SEV_RANK = {"high": 3, "medium": 2, "low": 1}
LGD, EARLY_ACTION_EFFECT = 0.45, 0.40


@router.get("/portfolio")
def portfolio(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    lake = get_lake()
    vm = visible_month(db)
    scores = lake.scores(vm)
    apps = db.query(Application).filter(Application.state == "MONITORING").all()
    open_alerts = db.query(Alert).filter(Alert.status == "OPEN").all()
    by_app: dict[int, list[Alert]] = {}
    for a in open_alerts:
        by_app.setdefault(a.application_id, []).append(a)

    consent = get_consent_provider(db)
    today = sim_date(db)
    rows = []
    for app in apps:
        p = lake.profile(app.factory_id)
        s = scores[scores.factory_id == app.factory_id].sort_values("month")
        cur = s.iloc[-1]
        prev = s[s.month == vm - 3]
        alerts = by_app.get(app.id, [])
        top = max(alerts, key=lambda a: SEV_RANK[a.severity]) if alerts else None
        rows.append({
            "application_id": app.id, "factory_id": app.factory_id, "name": p["name"], "sector": p["sector_label"],
            "cluster": p["cluster"], "udyam_category": p["udyam_category"], "exposure": app.sanctioned_limit or 0,
            "score": int(cur.score), "band": cur.band, "pd_12m": round(float(cur.pd_12m), 4),
            "trend_3m": int(cur.score - prev.score.iloc[0]) if not prev.empty else 0,
            "sparkline": [int(x) for x in s.score.tail(6)],
            "open_alerts": len(alerts), "max_severity": top.severity if top else None,
            "consent_active": consent.active(app.id, today) is not None,
        })

    sev_counts = {k: sum(1 for a in open_alerts if a.severity == k) for k in ("high", "medium", "low")}
    alerted = [r for r in rows if r["max_severity"] in ("high", "medium")]
    avoided = sum(r["exposure"] * r["pd_12m"] * LGD * EARLY_ACTION_EFFECT for r in alerted)

    cells: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        cells.setdefault((r["cluster"], r["sector"]), []).append(r)
    heatmap = [{"cluster": c, "sector": s, "accounts": len(v), "avg_score": round(sum(x["score"] for x in v) / len(v)),
                "alerts": sum(x["open_alerts"] for x in v)} for (c, s), v in sorted(cells.items())]
    return {
        "as_of": str(today), "data_month": month_label(vm),
        "kpis": {
            "accounts": len(rows),
            "avg_score": round(sum(r["score"] for r in rows) / len(rows)) if rows else None,
            "exposure": sum(r["exposure"] for r in rows),
            "alerts_by_severity": sev_counts,
            "expected_slippage_avoided": round(avoided),
            "slippage_formula": f"Σ exposure × PD × LGD {LGD} × early-action effect {EARLY_ACTION_EFFECT} "
                                "over accounts with open high/medium alerts",
        },
        "heatmap": heatmap,
        "accounts": sorted(rows, key=lambda r: (-SEV_RANK.get(r["max_severity"] or "", 0), r["score"])),
    }


@router.get("/alerts")
def list_alerts(status_filter: str | None = Query(default="OPEN", alias="status"), db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_roles(*STAFF))) -> list[dict]:
    lake = get_lake()
    q = db.query(Alert)
    if status_filter and status_filter != "ALL":
        q = q.filter(Alert.status == status_filter)
    alerts = sorted(q.all(), key=lambda a: (-SEV_RANK[a.severity], -a.month, a.id))
    out = []
    for a in alerts:
        p = lake.profile(a.factory_id)
        out.append({
            "id": a.id, "application_id": a.application_id, "factory_id": a.factory_id, "name": p["name"],
            "cluster": p["cluster"], "sector": p["sector_label"], "month": month_label(a.month),
            "severity": a.severity, "rules": a.rules, "reasons": a.reasons, "next_best_action": a.next_best_action,
            "briefing": a.briefing, "status": a.status, "action_taken": a.action_taken, "action_note": a.action_note,
            "actioned_by": a.actioned_by, "raised_on": str(a.raised_on), "ai_label": AI_LABEL,
        })
    return out


@router.post("/alerts/{alert_id}/action")
def action_alert(alert_id: int, body: AlertAction, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require_roles("rm", "credit_officer"))) -> dict:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert.status, alert.action_taken, alert.action_note, alert.actioned_by = "ACTIONED", body.action, body.note, user.username
    log_event(db, user, agent="api", tool="alerts", action="log_action",
              inputs={"alert_id": alert_id, "action": body.action, "note": body.note},
              output={"status": "ACTIONED"}, application_id=alert.application_id)
    return {"id": alert.id, "status": alert.status, "action_taken": alert.action_taken}


@router.get("/sim/clock")
def clock(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles(*STAFF, "msme"))) -> dict:
    return {"sim_date": str(sim_date(db)), "data_month": month_label(visible_month(db))}


@router.post("/sim/advance")
def advance(days: int = Query(default=7, ge=1, le=120), db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    """Fast-forward the simulated clock, then let the early-warning agent process newly visible data."""
    before = sim_date(db)
    after = set_sim_date(db, before + timedelta(days=days))
    run = EarlyWarningAgent(db, user).run()
    log_event(db, user, agent="api", tool="sim_clock", action="advance",
              inputs={"days": days, "from": str(before)}, output={"to": str(after), **run.to_dict()})
    return {"sim_date": str(after), "data_month": month_label(visible_month(db)), **run.to_dict()}
