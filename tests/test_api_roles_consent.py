from api.models.db import DataSnapshot, SessionLocal
from tests.conftest import hero_app_id, login


def test_requires_auth(client):
    assert client.get("/portfolio").status_code == 401


def test_full_journey_roles_and_audit(client):
    rm, co, risk = login(client, "rm1"), login(client, "co1"), login(client, "risk1")
    app_id = hero_app_id(client, rm)

    assert client.post(f"/applications/{app_id}/score", headers=rm).status_code == 403  # no consent yet
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    score = client.post(f"/applications/{app_id}/score", headers=rm).json()
    assert score["band"] == "APPROVE" and len(score["reasons"]) == 5
    assert "final decision by credit officer" in score["ai_label"]
    assert client.post(f"/applications/{app_id}/memo", headers=rm).status_code == 200

    body = {"decision": "APPROVED", "comment": "Approve per memo"}
    for who in (rm, risk):
        assert client.post(f"/applications/{app_id}/decision", headers=who, json=body).status_code == 403
    assert client.post(f"/applications/{app_id}/decision", headers=co,
                       json={"decision": "APPROVED", "comment": "  "}).status_code in (422, 400)
    r = client.post(f"/applications/{app_id}/decision", headers=co, json=body)
    assert r.status_code == 200 and r.json()["kfs"]["status"].startswith("STUB")
    assert client.post(f"/applications/{app_id}/disburse", headers=co).json()["state"] == "MONITORING"

    # Only risk can read the audit trail; every step is recorded there.
    assert client.get("/audit", headers=rm).status_code == 403
    assert client.get("/audit", headers=co).status_code == 403
    audit = client.get(f"/audit?application_id={app_id}&limit=2000", headers=risk).json()
    actions = {(a["agent"], a["tool"], a["action"]) for a in audit}
    assert ("orchestrator", "credit_decision", "approved") in actions
    assert ("orchestrator", "los_stub.disburse", "disburse") in actions
    assert any(a["tool"] == "scoring_engine.explain" for a in audit)
    assert any(a["tool"] == "llm.write" for a in audit)
    assert all(a["output_hash"] is None or len(a["output_hash"]) == 64 for a in audit)


def test_fast_forward_raises_high_alert_for_hero(client):
    rm = login(client, "rm1")
    for _ in range(6):
        client.post("/sim/advance?days=7", headers=rm)
    alerts = [a for a in client.get("/alerts", headers=rm).json() if a["factory_id"] == "UP-F0001"]
    assert alerts and alerts[0]["severity"] == "high"
    assert alerts[0]["next_best_action"] == "visit + limit review"
    r = client.post(f"/alerts/{alerts[0]['id']}/action", headers=rm, json={"action": "visit", "note": "Thu"})
    assert r.json()["status"] == "ACTIONED"


def test_msme_can_only_see_own_factory(client):
    msme = login(client, "sharma")
    assert client.get("/msme/UP-F0001/readiness", headers=msme).status_code == 200
    assert client.get("/msme/UP-F0002/readiness", headers=msme).status_code == 403
    assert client.get("/portfolio", headers=msme).status_code == 403


def test_revoking_consent_blocks_new_pulls(client):
    rm, msme = login(client, "rm1"), login(client, "sharma")
    app_id = client.get("/msme/UP-F0001/readiness", headers=msme).json()["application_id"]
    with SessionLocal() as db:
        assert db.query(DataSnapshot).filter_by(application_id=app_id).count() > 0

    assert client.delete(f"/applications/{app_id}/consent", headers=msme).json()["status"] == "REVOKED"

    r = client.get("/msme/UP-F0001/readiness", headers=msme).json()
    assert r["data_stale"] is True and r["plan"] is None
    assert client.post(f"/applications/{app_id}/score", headers=rm).status_code == 403
    run = client.post("/sim/advance?days=31", headers=rm).json()
    assert app_id in run["blocked"]

    ledger = [e["event"] for e in client.get(f"/applications/{app_id}/consent-ledger", headers=rm).json()]
    assert "REVOKED" in ledger and "DELETION_JOB" in ledger and "PULL_BLOCKED" in ledger
    with SessionLocal() as db:
        assert db.query(DataSnapshot).filter_by(application_id=app_id).count() == 0


def test_invalid_transition_is_rejected(client):
    rm, co = login(client, "rm1"), login(client, "co1")
    apps = [a for a in client.get("/applications", headers=rm).json() if a["state"] == "APPLIED"]
    app_id = apps[0]["id"]
    r = client.post(f"/applications/{app_id}/decision", headers=co, json={"decision": "APPROVED", "comment": "x ok"})
    assert r.status_code == 409
