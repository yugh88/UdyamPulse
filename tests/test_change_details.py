"""Plain detail lines in "What changed" and the month-over-month score change in the applications list."""

from __future__ import annotations

from tests.conftest import hero_app_id, login


def _hero(client, headers) -> dict:
    return next(a for a in client.get("/applications?limit=500", headers=headers).json() if a["factory_id"] == "UP-F0001")


def test_timeline_events_carry_a_plain_detail_line(client):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    assert client.post(f"/applications/{app_id}/score", headers=rm).status_code == 200
    assert client.post(f"/applications/{app_id}/memo", headers=rm).status_code == 200
    by = {e["event_type"]: e for e in client.get(f"/applications/{app_id}/changes", headers=rm).json()}
    assert by["opened"]["detail"].startswith("Asks for ₹")
    assert "data checks passed" in by["state_changed"]["detail"]
    assert "risk of default" in by["scored"]["detail"]
    assert "policy citation" in by["memo_ready"]["detail"] and by["memo_ready"]["detail"].startswith("Limit ₹")


def test_scored_applications_show_the_change_since_last_month(client):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    client.post(f"/applications/{app_id}/consent", headers=rm)
    client.post(f"/applications/{app_id}/score", headers=rm)
    hero = _hero(client, rm)
    trend = hero["score_trend"]
    assert trend is not None and trend["delta"] == hero["score"] - trend["prev"] and trend["since"]
    unscored = [a for a in client.get("/applications", headers=rm).json() if a["score"] is None]
    assert all(a["score_trend"] is None for a in unscored)
