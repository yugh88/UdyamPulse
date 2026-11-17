"""Attribute-based access: a branch relationship manager sees only the clusters it covers."""

from __future__ import annotations

from api.audit import Actor
from api.authz import branch_clusters
from tests.conftest import hero_app_id, login


def _apps(client, headers, state: str | None = None) -> list[dict]:
    path = "/applications" + (f"?state={state}&limit=500" if state else "?limit=500")
    r = client.get(path, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_branch_rm_sees_only_its_cluster(client):
    morbi, hub = login(client, "rm3"), login(client, "rm1")
    monitored_morbi = _apps(client, morbi, "MONITORING")
    monitored_all = _apps(client, hub, "MONITORING")
    assert monitored_morbi, "the seeded portfolio has Morbi accounts"
    assert {a["cluster"] for a in monitored_morbi} == {"Morbi"}
    assert len(monitored_morbi) < len(monitored_all)


def test_branch_rm_cannot_open_or_act_on_another_branch(client):
    morbi = login(client, "rm3")
    hero = hero_app_id(client, login(client, "rm1"))  # Ludhiana
    r = client.get(f"/applications/{hero}", headers=morbi)
    assert r.status_code == 403 and "branch" in r.json()["detail"]
    assert client.post(f"/applications/{hero}/consent", headers=morbi).status_code == 403
    assert client.post("/score/simulate", headers=morbi, json={"application_id": hero, "adjustments": {}}).status_code == 403


def test_branch_rm_alerts_are_scoped(client):
    morbi, hub = login(client, "rm3"), login(client, "rm1")
    mine = client.get("/alerts?status=ALL", headers=morbi).json()
    everything = client.get("/alerts?status=ALL", headers=hub).json()
    assert all(a["cluster"] == "Morbi" for a in mine)
    outside = [a for a in everything if a["cluster"] != "Morbi"]
    assert outside
    r = client.post(f"/alerts/{outside[0]['id']}/action", headers=morbi,
                    json={"action": "call", "note": "x", "outcome": "monitoring"})
    assert r.status_code == 403
    r = client.post("/alerts/bulk", headers=morbi, json={"ids": [outside[0]["id"]], "action": "acknowledge"})
    assert r.status_code == 403


def test_portfolio_views_follow_branch_scope(client):
    morbi, risk = login(client, "rm3"), login(client, "risk1")
    a = client.get("/portfolio", headers=morbi).json()
    b = client.get("/portfolio", headers=risk).json()
    assert a != b  # separate cache entries per scope, never one RM's view served to another


def test_scope_rules():
    assert branch_clusters(Actor("r", "risk", branch="Morbi")) is None  # risk is always bank-wide
    assert branch_clusters(Actor("c", "credit_officer")) is None  # hub by default
    assert branch_clusters(Actor("m", "rm")) == frozenset()  # an RM with no branch sees nothing
    assert branch_clusters(Actor("m", "rm", branch="*")) is None
    assert branch_clusters(Actor("m", "rm", branch="Morbi, Rajkot")) == {"Morbi", "Rajkot"}
