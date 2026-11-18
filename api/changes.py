"""Change tracking: what changed, from what, to what, when, and whether this user has seen it yet.

**Write side.** One `after_flush` listener turns every business change into a `ChangeEvent` with before/after
values and a plain-language summary. It covers every code path (API, agents, workers, the seed) without
call sites remembering to log:

| Entity | Events |
|---|---|
| application | `opened`, `state_changed`, `scored` / `score_changed`, `memo_ready` / `memo_updated`, `decided` |
| alert | `alert_raised`, `alert_actioned` |
| consent | `consent_granted`, `consent_revoked`, `consent_expired` |

Events are added during the flush and written by the same commit, so a rolled-back change leaves no event.

**Read side.** Each item carries `changed_since_seen`, `change_kind` ("new" | "updated" | null),
`prev_score` and `score_delta`. A user's last look at an item is `UserSeen.last_seen_at`. A "mark all seen"
row (`entity_id = "*"`) covers every item of that type. With no row at all, the baseline is the end of the
demo seed (`Tenant.change_baseline_at`), so seeded history starts unflagged and everything since is visible.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import event, func, inspect
from sqlalchemy.orm import Session

from api.models.db import Alert, Application, ChangeEvent, Consent, Tenant, UserSeen, utcnow

ACTOR_KEY = "change_actor"  # session.info key: who is making the change in this unit of work
STATE_TEXT = {
    "CONSENTED": "Consent received and data pulled",
    "SCORED": "Factory Health Score calculated",
    "MEMO_DRAFTED": "Credit memo drafted",
    "DECIDED": "Credit decision recorded",
    "DISBURSED": "Loan disbursed",
    "MONITORING": "Now under early-warning monitoring",
}
# What the account needs next, in plain words, and whose action it is.
NEXT_STEP = {
    "APPLIED": ("Ask for consent and pull data", "rm"),
    "CONSENTED": ("Run the health score", "rm"),
    "SCORED": ("Draft the credit memo", "rm"),
    "MEMO_DRAFTED": ("Memo ready: review and decide", "credit_officer"),
    "DECIDED": ("Approved: disburse via LOS", "credit_officer"),
    "DISBURSED": ("Disbursed: monitoring starts", None),
    "MONITORING": ("Monitoring", None),
}
SEVERITY_TEXT = {"high": "High", "medium": "Medium", "low": "Low"}
RULE_TEXT = {"order_loss": "order loss", "cash_squeeze": "cash squeeze", "buyer_risk": "buyer risk",
             "diversion": "possible diversion", "compliance_slip": "compliance slip"}


def set_actor(session: Session, username: str) -> None:
    session.info[ACTOR_KEY] = username


def _aware(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)  # SQLite returns naive UTC


# ---------------------------------------------------------------- write side

def _history(obj, attr: str) -> tuple[object, object] | None:
    """(before, after) when `attr` changed in this flush, else None."""
    h = inspect(obj).attrs[attr].history
    if not h.added and not h.deleted:
        return None
    before = h.deleted[0] if h.deleted else None
    after = h.added[0] if h.added else None
    return None if before == after else (before, after)


def _band(b: str | None) -> str:
    return {"APPROVE": "Approve", "WATCH": "Watch", "HIGH_RISK": "High risk"}.get(b or "", b or "–")


def _application_events(app: Application, is_new: bool) -> list[dict]:
    if is_new:
        return [{"event_type": "opened", "before": None, "after": {"state": app.state},
                 "summary": "Application opened"}]
    out: list[dict] = []
    if (score := _history(app, "score")) is not None:
        before, after = score
        band = _history(app, "band")
        band_before = band[0] if band else app.band
        if before is None:
            summary = f"Scored {after} ({_band(app.band)})"
            kind = "scored"
        else:
            summary = f"Score {before} → {after}"
            if band:
                summary += f" ({_band(band_before)} → {_band(app.band)})"
            kind = "score_changed"
        out.append({"event_type": kind, "before": {"score": before, "band": band_before},
                    "after": {"score": after, "band": app.band}, "summary": summary})
    if (memo := _history(app, "memo")) is not None and memo[1] is not None:
        first = memo[0] is None
        out.append({"event_type": "memo_ready" if first else "memo_updated", "before": None,
                    "after": {"recommended_limit": app.recommended_limit, "pricing_band": app.pricing_band},
                    "summary": "Credit memo ready for review" if first else "Credit memo redrafted"})
    if (decision := _history(app, "decision")) is not None and decision[1]:
        verb = "Approved" if decision[1] == "APPROVED" else "Rejected"
        out.append({"event_type": "decided", "before": {"decision": decision[0]},
                    "after": {"decision": decision[1], "sanctioned_limit": app.sanctioned_limit},
                    "summary": f"{verb} by {app.decided_by or 'credit officer'}"})
    if (state := _history(app, "state")) is not None:
        before, after = state
        if after not in ("SCORED", "MEMO_DRAFTED", "DECIDED"):  # those already have richer events above
            out.append({"event_type": "state_changed", "before": {"state": before}, "after": {"state": after},
                        "summary": STATE_TEXT.get(after, f"Moved to {after}")})
    return out


def _alert_events(alert: Alert, is_new: bool) -> list[dict]:
    if is_new:
        rules = ", ".join(RULE_TEXT.get(r, r) for r in (alert.rules or [])) or "unusual pattern"
        return [{"event_type": "alert_raised", "before": None,
                 "after": {"severity": alert.severity, "rules": alert.rules, "status": alert.status},
                 "summary": f"{SEVERITY_TEXT.get(alert.severity, alert.severity)} alert: {rules}"}]
    if (status := _history(alert, "status")) is not None and status[1] == "ACTIONED":
        return [{"event_type": "alert_actioned", "before": {"status": status[0]},
                 "after": {"status": "ACTIONED", "action": alert.action_taken, "outcome": alert.outcome},
                 "summary": f"Alert actioned: {alert.action_taken or 'action logged'}"}]
    return []


def _consent_events(consent: Consent, is_new: bool) -> list[dict]:
    if is_new:
        return [{"event_type": "consent_granted", "before": None, "after": {"status": consent.status},
                 "summary": "Consent granted for data sharing"}]
    if (status := _history(consent, "status")) is not None:
        after = status[1]
        if after in ("REVOKED", "EXPIRED"):
            return [{"event_type": f"consent_{after.lower()}", "before": {"status": status[0]},
                     "after": {"status": after},
                     "summary": "Consent revoked: data sharing stopped" if after == "REVOKED" else "Consent expired"}]
    return []


@event.listens_for(Session, "after_flush")
def _record_changes(session: Session, _ctx) -> None:
    actor = session.info.get(ACTOR_KEY, "system")
    new = set(session.new)
    pending: list[ChangeEvent] = []
    for obj in list(new) + list(session.dirty):
        is_new = obj in new
        if isinstance(obj, Application):
            items, etype, eid, app_id = _application_events(obj, is_new), "application", str(obj.id), obj.id
        elif isinstance(obj, Alert):
            items, etype, eid, app_id = _alert_events(obj, is_new), "alert", str(obj.id), obj.application_id
        elif isinstance(obj, Consent):
            items, etype, eid, app_id = _consent_events(obj, is_new), "consent", str(obj.id), obj.application_id
        else:
            continue
        for it in items:
            pending.append(ChangeEvent(entity_type=etype, entity_id=eid, application_id=app_id, actor=actor,
                                       tenant_id=obj.tenant_id, **it))
    for ev in pending:  # written by the commit's next flush pass, inside the same transaction
        session.add(ev)


# ---------------------------------------------------------------- read side

def _baseline(db: Session, tenant_id: str | None) -> datetime:
    t = db.get(Tenant, tenant_id) if tenant_id else None
    return _aware(t.change_baseline_at) if t and t.change_baseline_at else datetime(1970, 1, 1, tzinfo=UTC)


def seen_map(db: Session, username: str, entity_type: str) -> dict[str, datetime]:
    rows = db.query(UserSeen).filter(UserSeen.username == username, UserSeen.entity_type == entity_type).all()
    return {r.entity_id: _aware(r.last_seen_at) for r in rows}


def latest_events(db: Session, entity_type: str, ids: Iterable[str]) -> dict[str, datetime]:
    ids = list(ids)
    if not ids:
        return {}
    rows = (db.query(ChangeEvent.entity_id, func.max(ChangeEvent.created_at))
            .filter(ChangeEvent.entity_type == entity_type, ChangeEvent.entity_id.in_(ids))
            .group_by(ChangeEvent.entity_id).all())
    return {eid: _aware(ts) for eid, ts in rows}


def previous_scores(db: Session, app_ids: Iterable[int]) -> dict[int, int | None]:
    """The score before the most recent score change, per application."""
    ids = list(app_ids)
    if not ids:
        return {}
    rows = (db.query(ChangeEvent).filter(ChangeEvent.entity_type == "application",
                                         ChangeEvent.event_type == "score_changed",
                                         ChangeEvent.application_id.in_(ids))
            .order_by(ChangeEvent.id).all())
    out: dict[int, int | None] = {}
    for r in rows:
        out[r.application_id] = (r.before or {}).get("score")
    return out


class ChangeFlags:
    """Computes `changed_since_seen` / `change_kind` for many items of one type in three queries."""

    def __init__(self, db: Session, username: str, tenant_id: str | None, entity_type: str, ids: Iterable[str]):
        self.entity_type = entity_type
        self.seen = seen_map(db, username, entity_type)
        self.base = max(self.seen.get("*") or _baseline(db, tenant_id), _baseline(db, tenant_id))
        self.latest = latest_events(db, entity_type, ids)

    def last_seen(self, entity_id: str) -> datetime:
        own = self.seen.get(entity_id)
        return max(own, self.base) if own else self.base

    def kind(self, entity_id: str, created_at: datetime | None) -> str | None:
        seen = self.last_seen(entity_id)
        if created_at and _aware(created_at) > seen:
            return "new"
        latest = self.latest.get(entity_id)
        return "updated" if latest and latest > seen else None


def next_step(app: Application, role: str) -> dict:
    text, owner = NEXT_STEP.get(app.state, (app.state, None))
    return {"text": text, "owner_role": owner, "yours": owner == role}


def application_change_fields(db: Session, user, apps: list[Application]) -> dict[int, dict]:
    flags = ChangeFlags(db, user.username, user.tenant_id, "application", [str(a.id) for a in apps])
    prev = previous_scores(db, [a.id for a in apps])
    out = {}
    for a in apps:
        kind = flags.kind(str(a.id), a.created_at)
        p = prev.get(a.id)
        out[a.id] = {"changed_since_seen": kind is not None, "change_kind": kind, "prev_score": p,
                     "score_delta": (a.score - p) if (a.score is not None and p is not None) else None,
                     "next_step": next_step(a, user.role)}
    return out


def timeline(db: Session, user, app: Application, limit: int = 100) -> list[dict]:
    """Plain-language history of one application, newest first, with `new` for entries after the user's last look."""
    flags = ChangeFlags(db, user.username, user.tenant_id, "application", [str(app.id)])
    seen = flags.last_seen(str(app.id))
    rows = (db.query(ChangeEvent).filter(ChangeEvent.application_id == app.id)
            .order_by(ChangeEvent.id.desc()).limit(limit).all())
    return [{"id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id, "event_type": r.event_type,
             "summary": r.summary, "before": r.before, "after": r.after, "actor": r.actor,
             "created_at": _aware(r.created_at).isoformat(), "new": _aware(r.created_at) > seen} for r in rows]


def mark_seen(db: Session, user, entity_type: str, entity_ids: list[str]) -> int:
    now = utcnow()
    existing = {r.entity_id: r for r in db.query(UserSeen).filter(
        UserSeen.username == user.username, UserSeen.entity_type == entity_type,
        UserSeen.entity_id.in_(entity_ids)).all()}
    for eid in entity_ids:
        row = existing.get(eid)
        if row is None:
            db.add(UserSeen(username=user.username, entity_type=entity_type, entity_id=eid, last_seen_at=now))
        else:
            row.last_seen_at = now
    return len(entity_ids)


def tile(value, prev, period: str, good_when_up: bool) -> dict:
    delta = (value - prev) if (value is not None and prev is not None) else None
    if isinstance(delta, float):
        delta = round(delta, 4)
    return {"value": value, "prev_value": prev, "delta": delta, "period": period, "good_when_up": good_when_up}
