"""Change tracking: events per change, before → after, deltas, seen / unseen, scope, and live stream filtering."""

from __future__ import annotations

from api.models.db import Application, ChangeEvent, SessionLocal
from api.tenancy import bind_tenant
from tests.conftest import advance, hero_app_id, login


def _hero_id() -> int:
    """The hero's application id, whatever its state (the default list hides monitored accounts)."""
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        return db.query(Application.id).filter(Application.factory_id == "UP-F0001").order_by(Application.id).first()[0]


def _hero(client, headers) -> dict:
    rows = client.get("/applications?limit=500", headers=headers).json()
    rows += client.get("/applications?state=MONITORING&limit=500", headers=headers).json()
    rows += client.get("/applications?state=DECIDED&limit=500", headers=headers).json()
    return next(a for a in rows if a["factory_id"] == "UP-F0001")


def _events(app_id: int) -> list[ChangeEvent]:
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        return db.query(ChangeEvent).filter(ChangeEvent.application_id == app_id).order_by(ChangeEvent.id).all()


def test_seeded_history_is_not_flagged(client):
    rows = client.get("/applications", headers=login(client, "rm1")).json()
    assert rows and not any(r["changed_since_seen"] for r in rows)
    hero = _hero(client, login(client, "rm1"))
    assert hero["next_step"] == {"text": "Ask for consent and pull data", "owner_role": "rm", "yours": True}


def test_every_change_writes_an_event_with_before_after_and_actor(client):
    rm, co = login(client, "rm1"), login(client, "co1")
    app_id = hero_app_id(client, rm)
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    score = client.post(f"/applications/{app_id}/score", headers=rm).json()["score"]
    assert client.post(f"/applications/{app_id}/memo", headers=rm).status_code == 200
    r = client.post(f"/applications/{app_id}/decision", headers=co,
                    json={"decision": "APPROVED", "comment": "Approve per memo."})
    assert r.status_code == 200, r.text
    kinds = [e.event_type for e in _events(app_id)]
    for expected in ("consent_granted", "state_changed", "scored", "memo_ready", "decided"):
        assert expected in kinds, (expected, kinds)
    by = {e.event_type: e for e in _events(app_id)}
    assert by["scored"].after["score"] == score and by["scored"].before["score"] is None
    assert by["scored"].summary.startswith(f"Scored {score}")
    assert by["decided"].actor == "co1" and by["decided"].after["decision"] == "APPROVED"
    assert by["consent_granted"].actor == "rm1"

    # The credit officer has not looked yet, so the hero is flagged; looking clears it.
    hero = _hero(client, co)
    assert hero["changed_since_seen"] and hero["change_kind"] == "updated"
    timeline = client.get(f"/applications/{app_id}/changes", headers=co).json()
    assert timeline[0]["new"] and timeline[0]["summary"].startswith("Approved")
    assert client.post("/seen", headers=co, json={"entity_type": "application", "ids": [str(app_id)]}).status_code == 200
    assert not _hero(client, co)["changed_since_seen"]
    assert not any(e["new"] for e in client.get(f"/applications/{app_id}/changes", headers=co).json())


def test_alerts_carry_before_after_and_score_delta_direction(client):
    rm = login(client, "rm1")
    app_id = _hero_id()
    client.post(f"/applications/{app_id}/disburse", headers=login(client, "co1"))
    advance(client, rm, 42)
    alerts = client.get("/alerts", headers=rm).json()
    hero = next(a for a in alerts if a["factory_id"] == "UP-F0001" and a["severity"] == "high")
    assert hero["change_kind"] == "new"
    detail = client.get(f"/alerts/{hero['id']}", headers=rm).json()
    eway = next(s for s in detail["signals"] if s["key"] == "eway_value")
    assert eway["after"] < eway["before"] and eway["good_when_up"] is True  # dispatches fell: worse
    assert detail["score"]["after"] < detail["score"]["before"]
    kinds = [e.event_type for e in _events(app_id)]
    assert "alert_raised" in kinds
    # Logging an action records it; mark-all-seen clears every alert marker.
    r = client.post(f"/alerts/{hero['id']}/action", headers=rm, json={"action": "visit", "note": "Visited", "outcome": "monitoring"})
    assert r.status_code == 200
    assert "alert_actioned" in [e.event_type for e in _events(app_id)]
    client.post("/seen", headers=rm, json={"entity_type": "alert", "all": True})
    assert not any(a["changed_since_seen"] for a in client.get("/alerts?status=ALL", headers=rm).json())


def test_stat_tiles_have_value_previous_delta_and_period(client):
    tiles = client.get("/applications/stats", headers=login(client, "co1")).json()["tiles"]
    for key in ("waiting_on_you", "avg_hours_to_memo", "approval_rate_30d"):
        assert {"value", "prev_value", "delta", "period", "good_when_up"} <= set(tiles[key])
    w = tiles["waiting_on_you"]
    assert w["good_when_up"] is False and w["period"] == "since yesterday"
    if w["prev_value"] is not None:
        assert w["delta"] == w["value"] - w["prev_value"]


def test_branch_scope_applies_to_timelines_and_the_live_stream(client):
    from api.routers.jobs import _poll_changes

    rm3 = login(client, "rm3")
    app_id = _hero_id()  # Ludhiana: outside the Morbi branch
    assert client.get(f"/applications/{app_id}/changes", headers=rm3).status_code == 403

    class U:  # minimal stand-ins for the authenticated users
        tenant_id, factory_id = "bank-a", None

    hub, morbi = U(), U()
    hub.username, hub.role, hub.branch = "rm1", "rm", "*"
    morbi.username, morbi.role, morbi.branch = "rm3", "rm", "Morbi"
    mark, _ = _poll_changes(hub, None)
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        app = db.get(Application, app_id)
        app.review_note, app.score = "touch", (app.score or 600) + 1
        db.commit()
    _, seen_by_hub = _poll_changes(hub, mark)
    _, seen_by_morbi = _poll_changes(morbi, mark)
    assert any(c["application_id"] == app_id for c in seen_by_hub)
    assert not any(c["application_id"] == app_id for c in seen_by_morbi)


def test_rolled_back_changes_leave_no_event(client):
    app_id = _hero_id()
    before = len(_events(app_id))
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        app = db.get(Application, app_id)
        app.score = 1
        db.flush()
        db.rollback()
    assert len(_events(app_id)) == before
