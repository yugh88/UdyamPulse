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
from api.models.db import Alert, Application, User, get_db, utcnow
from api.models.schemas import AlertAction, AlertBulk
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


BAND_ORDER = ("APPROVE", "WATCH", "HIGH_RISK")


@router.get("/portfolio/migration")
def migration(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    """Score-band migration of monitored accounts between the previous and the latest visible month."""
    lake = get_lake()
    vm = visible_month(db)
    apps = db.query(Application).filter(Application.state == "MONITORING").all()
    by_factory = {a.factory_id: a for a in apps}
    scores = lake.scores(vm)
    scores = scores[scores.factory_id.isin(set(by_factory)) & scores.month.isin([vm - 1, vm])]
    prev = scores[scores.month == vm - 1].set_index("factory_id")
    cur = scores[scores.month == vm].set_index("factory_id")
    matrix = {a: {b: 0 for b in BAND_ORDER} for a in BAND_ORDER}
    movers = []
    for fid in cur.index.intersection(prev.index):
        a, b = prev.loc[fid, "band"], cur.loc[fid, "band"]
        matrix[a][b] += 1
        if a != b:
            movers.append({"application_id": by_factory[fid].id, "factory_id": fid, "name": lake.profile(fid)["name"],
                           "from_band": a, "to_band": b, "from_score": int(prev.loc[fid, "score"]),
                           "to_score": int(cur.loc[fid, "score"]),
                           "direction": "down" if BAND_ORDER.index(b) > BAND_ORDER.index(a) else "up"})
    movers.sort(key=lambda m: m["to_score"] - m["from_score"])
    return {
        "from_month": month_label(vm - 1), "to_month": month_label(vm), "bands": list(BAND_ORDER), "matrix": matrix,
        "accounts": int(len(cur.index.intersection(prev.index))),
        "downgrades": sum(1 for m in movers if m["direction"] == "down"),
        "upgrades": sum(1 for m in movers if m["direction"] == "up"),
        "movers": movers,
    }


@router.get("/staff")
def staff(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles(*STAFF))) -> list[dict]:
    """Staff who can own an alert (for the assign menu)."""
    rows = db.query(User).filter(User.role.in_(("rm", "credit_officer"))).order_by(User.username).all()
    return [{"username": u.username, "display_name": u.display_name, "role": u.role} for u in rows]


@router.get("/alerts")
def list_alerts(status_filter: str | None = Query(default="OPEN", alias="status"), db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_roles(*STAFF))) -> list[dict]:
    lake = get_lake()
    q = db.query(Alert)
    if status_filter and status_filter != "ALL":
        q = q.filter(Alert.status == status_filter)
    alerts = sorted(q.all(), key=lambda a: (-SEV_RANK[a.severity], -a.month, a.id))
    today = sim_date(db)
    app_ids = {a.application_id for a in alerts}
    exposure = {x.id: x.sanctioned_limit or 0 for x in db.query(Application).filter(Application.id.in_(app_ids))}
    history: dict[int, list[Alert]] = {}
    for h in db.query(Alert).filter(Alert.application_id.in_(app_ids)).order_by(Alert.month, Alert.id):
        history.setdefault(h.application_id, []).append(h)
    out = []
    for a in alerts:
        p = lake.profile(a.factory_id)
        out.append({
            "owner": a.owner, "acknowledged_by": a.acknowledged_by, "outcome": a.outcome,
            "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            "days_open": max((today - a.raised_on).days, 0), "exposure": exposure.get(a.application_id, 0),
            "timeline": [{"id": h.id, "month": month_label(h.month), "severity": h.severity, "rules": h.rules,
                          "reasons": h.reasons, "status": h.status, "action_taken": h.action_taken,
                          "raised_on": str(h.raised_on)} for h in history.get(a.application_id, [])],
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
    alert.outcome = body.outcome
    alert.owner = alert.owner or user.username
    log_event(db, user, agent="api", tool="alerts", action="log_action",
              inputs={"alert_id": alert_id, "action": body.action, "note": body.note, "outcome": body.outcome},
              output={"status": "ACTIONED"}, application_id=alert.application_id)
    db.commit()
    return {"id": alert.id, "status": alert.status, "action_taken": alert.action_taken}


@router.post("/alerts/bulk")
def bulk_alerts(body: AlertBulk, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_roles("rm", "credit_officer"))) -> dict:
    """Assign an owner to, or acknowledge, several open alerts in one step."""
    if body.action == "assign":
        owner = db.query(User).filter_by(username=body.owner or "").one_or_none()
        if owner is None or owner.role not in ("rm", "credit_officer"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Owner must be a relationship manager or credit officer")
    alerts = db.query(Alert).filter(Alert.id.in_(body.ids), Alert.status == "OPEN").all()
    for a in alerts:
        if body.action == "assign":
            a.owner = body.owner
        else:
            a.acknowledged_by, a.acknowledged_at = user.username, utcnow()
            a.owner = a.owner or user.username
    log_event(db, user, agent="api", tool="alerts", action=f"bulk_{body.action}",
              inputs={"alert_ids": sorted(a.id for a in alerts), "owner": body.owner},
              output={"updated": len(alerts)})
    db.commit()
    return {"updated": len(alerts), "skipped": len(set(body.ids)) - len(alerts)}


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
    db.commit()
    return {"sim_date": str(after), "data_month": month_label(visible_month(db)), **run.to_dict()}
