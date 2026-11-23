from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from agents.base import sim_date, visible_month
from agents.memo_agent import AI_LABEL
from agents.orchestrator import Orchestrator
from agents.providers.consent import get_consent_provider
from agents.providers.lake import get_lake
from api import pagination
from api.audit import log_event
from api.auth import CurrentUser, ensure_factory_access, get_current_user, require_roles
from api.authz import ensure_branch_access, scope_applications
from api.changes import application_change_fields, tile, timeline
from api.jobs import enqueue
from api.models.db import Alert, Application, AuditLog, ChangeEvent, ConsentEvent, get_db, utcnow
from api.models.schemas import ApplicationCreate, DecisionRequest, ReviewRequest, ScoreResponse
from core.settings import get_settings
from core.timeline import month_label
from ml.features import format_value

router = APIRouter(prefix="/applications", tags=["applications"])
STAFF = ("rm", "credit_officer", "risk")


def _get_app(db: Session, app_id: int, user: CurrentUser) -> Application:
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    ensure_factory_access(user, app.factory_id)
    ensure_branch_access(user, app)
    return app


def _summary(app: Application, profile: dict) -> dict:
    return {
        "id": app.id, "factory_id": app.factory_id, "name": profile["name"], "sector": profile["sector_label"],
        "cluster": profile["cluster"], "udyam_category": profile["udyam_category"], "state": app.state,
        "requested_amount": app.requested_amount, "score": app.score, "band": app.band, "decision": app.decision,
        "channel": app.channel, "created_at": app.created_at.isoformat() if app.created_at else None,
        "last_activity": (app.updated_at or app.created_at).isoformat() if (app.updated_at or app.created_at) else None,
        "pd_12m": app.pd_12m, "review_requested": app.review_requested,
    }


SIGNAL_COLUMNS = ("eway_value", "einvoice_value", "open_po_value", "aa_credits", "aa_debits", "avg_balance", "bounces",
                  "kwh", "rm_purchases", "epfo_headcount", "avg_days_to_pay", "top_buyer_share",
                  "gst_filing_delay_days", "gst_bank_mismatch")
PEER_FEATURES = (("eway_value_chg_3v12", "E-way bill value, 3m vs 12m"), ("kwh_chg_3v12", "Electricity use, 3m vs 12m"),
                 ("net_inflow_ratio_3", "Net bank inflow margin (3m)"), ("bounces_12", "Bounces in 12 months"),
                 ("days_to_pay_3", "Days buyers take to pay (3m)"), ("top_buyer_share_1", "Top-buyer share of sales"))


def _signals(hist) -> list[dict]:
    out = []
    for r in hist.itertuples():
        row = {"month": month_label(int(r.month))}
        for c in SIGNAL_COLUMNS:
            v = float(getattr(r, c))
            row[c] = round(v, 4) if c in ("top_buyer_share", "gst_bank_mismatch") else round(v)
        out.append(row)
    return out


def _peers(lake, factory_id: str, cluster: str, month: int, score: int | None) -> dict:
    """This factory against the median of the other factories in the same cluster, same month."""
    profiles = lake.profiles()
    ids = set(profiles[profiles.cluster == cluster].factory_id) - {factory_id}
    gold = lake.features_month(month)
    peers = gold[gold.factory_id.isin(ids)]
    mine = gold[gold.factory_id == factory_id]
    scores = lake.scores(month)
    peer_scores = scores[(scores.month == month) & scores.factory_id.isin(ids)]
    rows = []
    if score is not None and not peer_scores.empty:
        rows.append({"metric": "score", "label": "Factory Health Score", "value": str(score),
                     "peer_median": str(int(peer_scores.score.median()))})
    if not mine.empty and not peers.empty:
        for name, label in PEER_FEATURES:
            rows.append({"metric": name, "label": label, "value": format_value(name, float(mine[name].iloc[0])),
                         "peer_median": format_value(name, float(peers[name].median()))})
    return {"cluster": cluster, "peer_count": len(ids), "month": month_label(month), "rows": rows}


ROLE_QUEUE = {"rm": {"APPLIED", "CONSENTED", "SCORED"}, "credit_officer": {"MEMO_DRAFTED", "DECIDED"},
              "risk": {"MEMO_DRAFTED"}}
EVENT_STATE = {"scored": "SCORED", "memo_ready": "MEMO_DRAFTED", "decided": "DECIDED"}


def _aware(ts):
    from datetime import UTC

    return ts if ts is None or ts.tzinfo else ts.replace(tzinfo=UTC)


def _tiles(db: Session, user: CurrentUser, apps: list[Application]) -> dict:
    """Stat tiles with value, previous value, delta and period, all from recorded change events."""
    from datetime import timedelta

    now = utcnow()
    ids = [a.id for a in apps]
    events = (db.query(ChangeEvent).filter(ChangeEvent.entity_type == "application",
                                           ChangeEvent.application_id.in_(ids)).order_by(ChangeEvent.id).all()
              if ids else [])
    queue = ROLE_QUEUE.get(user.role, set())

    def state_at(app: Application, when) -> str | None:
        if app.created_at and _aware(app.created_at) > when:
            return None
        state = None
        for e in events:
            if e.application_id != app.id or _aware(e.created_at) > when:
                continue
            state = (e.after or {}).get("state") or EVENT_STATE.get(e.event_type, state)
        return state

    waiting_now = sum(1 for a in apps if a.state in queue)
    day_ago = now - timedelta(days=1)
    waiting_prev = sum(1 for a in apps if state_at(a, day_ago) in queue) if events else None

    created = {a.id: _aware(a.created_at) for a in apps}

    def memo_hours(lo, hi) -> float | None:
        hrs = [(_aware(e.created_at) - created[e.application_id]).total_seconds() / 3600 for e in events
               if e.event_type == "memo_ready" and lo <= _aware(e.created_at) < hi and created.get(e.application_id)]
        return round(sum(hrs) / len(hrs), 2) if hrs else None

    def approval(lo, hi) -> float | None:
        ds = [e for e in events if e.event_type == "decided" and lo <= _aware(e.created_at) < hi]
        return round(sum(1 for e in ds if (e.after or {}).get("decision") == "APPROVED") / len(ds), 4) if ds else None

    d30, d60 = now - timedelta(days=30), now - timedelta(days=60)
    return {
        "waiting_on_you": tile(waiting_now, waiting_prev, "since yesterday", good_when_up=False),
        "avg_hours_to_memo": tile(memo_hours(d30, now), memo_hours(d60, d30), "last 30 days vs the 30 before",
                                  good_when_up=False),
        "approval_rate_30d": tile(approval(d30, now), approval(d60, d30), "last 30 days vs the 30 before",
                                  good_when_up=True),
    }


@router.get("/stats")
def application_stats(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles(*STAFF))) -> dict:
    """KPI tiles for the console. Decision figures count only decisions made in this system (not seed data)."""
    apps = scope_applications(db.query(Application), user).all()
    pending = [a for a in apps if a.state != "MONITORING" and a.decision is None]
    decided = [a for a in apps if a.decided_at is not None]
    approved = sum(1 for a in decided if a.decision == "APPROVED")
    hours = [(a.decided_at - a.created_at).total_seconds() / 3600 for a in decided if a.created_at]
    midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    scored_today = (db.query(AuditLog.application_id).filter(AuditLog.tool == "scoring_engine.explain",
                                                             AuditLog.ts >= midnight).distinct().count())
    return {
        "tiles": _tiles(db, user, apps),
        "pending": len(pending),
        "needs_decision": sum(1 for a in pending if a.state == "MEMO_DRAFTED"),
        "scored_today": scored_today,
        "decisions": len(decided),
        "approval_rate": round(approved / len(decided), 4) if decided else None,
        "avg_decision_hours": round(sum(hours) / len(hours), 2) if hours else None,
        "review_requested": sum(1 for a in apps if a.review_requested),
    }


@router.get("")
def list_applications(request: Request, response: Response, state: str | None = None,
                      limit: int = Query(default=200, ge=1, le=500), cursor: str | None = None,
                      db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles(*STAFF))) -> list[dict]:
    """Applications in the pipeline (or in one `state`), oldest first. Paginated by cursor (see `Link`)."""
    lake = get_lake()
    q = scope_applications(db.query(Application), user)
    q = q.filter(Application.state == state) if state else q.filter(Application.state != "MONITORING")
    after = pagination.decode(cursor, 1)
    if after:
        q = q.filter(Application.id > after[0])
    rows = q.order_by(Application.id).limit(limit + 1).all()
    page = rows[:limit]
    pagination.link_next(request, response, [page[-1].id] if len(rows) > limit else None)
    changes = application_change_fields(db, user, page)
    trends = _score_trends(db, lake, page)
    return [{**_summary(a, lake.profile(a.factory_id)), **changes[a.id], "score_trend": trends.get(a.id)} for a in page]


def _score_trends(db: Session, lake, apps: list[Application]) -> dict[int, dict]:
    """Score change against last month's score for each scored application (the same comparison as the overview)."""
    scored = [a for a in apps if a.score is not None]
    if not scored:
        return {}
    vm = visible_month(db)
    sc = lake.scores(vm)
    prev = sc[(sc.month == vm - 1) & sc.factory_id.isin({a.factory_id for a in scored})]
    by_factory = dict(zip(prev.factory_id, prev.score.astype(int), strict=True))
    out = {}
    for a in scored:
        p = by_factory.get(a.factory_id)
        if p is not None:
            out[a.id] = {"prev": p, "delta": int(a.score) - p, "since": month_label(vm - 1)}
    return out


@router.post("", status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require_roles("rm", "msme"))) -> dict:
    ensure_factory_access(user, body.factory_id)
    try:
        app = Orchestrator(db, user).create(body.factory_id, body.requested_amount, body.channel)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown factory {body.factory_id}") from exc
    return _summary(app, get_lake().profile(app.factory_id))


@router.get("/{app_id}/changes")
def application_changes(app_id: int, limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """What changed on this application, newest first, in plain language. `new` marks entries the caller
    has not seen yet."""
    return timeline(db, user, _get_app(db, app_id, user), limit)


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)) -> dict:
    app = _get_app(db, app_id, user)
    lake = get_lake()
    profile = lake.profile(app.factory_id)
    consent = get_consent_provider(db).active(app.id, sim_date(db))
    signals, score_history, stress_start, peers = [], [], None, None
    if consent:  # signals are only shown while consent is active
        vm = visible_month(db)
        signals = _signals(lake.history(app.factory_id, vm))
        sc = lake.scores(vm)
        sc = sc[sc.factory_id == app.factory_id].sort_values("month")
        score_history = [{"month": month_label(int(r.month)), "score": int(r.score), "band": r.band}
                         for r in sc.itertuples()]
        hits = lake.ews_hits(app.factory_id, list(range(max(1, vm - 11), vm + 1)))
        stressed = hits[hits.severity.isin(["medium", "high"])]
        if not stressed.empty:
            first = stressed.iloc[0]
            stress_start = {"month": month_label(int(first.month)), "severity": first.severity}
        if user.role != "msme":
            peers = _peers(lake, app.factory_id, profile["cluster"], vm, int(sc.score.iloc[-1]) if len(sc) else None)
    alerts = db.query(Alert).filter_by(application_id=app.id).order_by(Alert.month.desc()).all()
    return {
        **_summary(app, profile),
        "profile": {k: profile[k] for k in ("vintage_years", "turnover_band", "annual_turnover_cr", "n_buyers",
                                            "udyam_number")},
        "consent": get_consent_provider(db).summary(app.id, sim_date(db)),
        "data_checks": app.data_checks,
        "score_detail": app.score_detail,
        "memo": {k: v for k, v in (app.memo or {}).items() if k != "facts"} or None,
        "memo_pdf_url": f"/applications/{app.id}/memo.pdf" if app.memo_pdf else None,
        "pricing_band": app.pricing_band, "recommended_limit": app.recommended_limit,
        "decision_comment": app.decision_comment, "decided_by": app.decided_by, "kfs": app.kfs,
        "sanctioned_limit": app.sanctioned_limit, "disbursement_ref": app.disbursement_ref,
        "disbursed_on": str(app.disbursed_on) if app.disbursed_on else None,
        "signals": signals, "score_history": score_history, "stress_start": stress_start, "peers": peers,
        "decided_at": app.decided_at.isoformat() if app.decided_at else None,
        "review_note": app.review_note,
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


def _wants_async(prefer: str | None) -> bool:
    """RFC 7240: `Prefer: respond-async` asks for 202 + a job instead of waiting for the result."""
    return bool(prefer) and "respond-async" in prefer.lower()


def _accepted(db: Session, user: CurrentUser, kind: str, app: Application) -> JSONResponse:
    job = enqueue(db, user, kind, application_id=app.id)
    db.commit()
    return JSONResponse(status_code=202, headers={"Location": f"/v1/jobs/{job.id}", "Preference-Applied": "respond-async"},
                        content={"job_id": job.id, "status": "queued", "status_url": f"/v1/jobs/{job.id}"})


@router.post("/{app_id}/score", response_model=ScoreResponse,
             responses={202: {"description": "Queued as a background job (with `Prefer: respond-async`)"}})
def score_application(app_id: int, prefer: str | None = Header(default=None), db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require_roles("rm", "credit_officer"))):
    app = _get_app(db, app_id, user)
    if _wants_async(prefer):
        return _accepted(db, user, "application.score", app)
    result = Orchestrator(db, user).score(app)
    return {**result, "ai_label": AI_LABEL}


@router.post("/{app_id}/memo", responses={202: {"description": "Queued as a background job (with `Prefer: respond-async`)"}})
def draft_memo(app_id: int, prefer: str | None = Header(default=None), db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_roles("rm", "credit_officer"))):
    app = _get_app(db, app_id, user)
    if _wants_async(prefer):
        return _accepted(db, user, "application.memo", app)
    memo = Orchestrator(db, user).draft_memo(app)
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
    db.commit()
    return {"status": "Review requested — a credit officer will respond", "application_id": app.id}
