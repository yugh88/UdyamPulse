"""Tenant isolation: bank B can never read or change bank A's data, by listing, by id, or by guessing."""

import pytest

from api.models.db import Alert, Application, AuditLog, SessionLocal, Tenant, User
from api.tenancy import ENFORCE_KEY, TenantIsolationError, allow_cross_tenant, bind_tenant
from tests.conftest import hero_app_id, login


def test_each_bank_sees_only_its_own_portfolio(client):
    a, b = login(client, "rm1"), login(client, "rm2")
    apps_a = {x["id"] for x in client.get("/applications", headers=a).json()}
    apps_b = {x["id"] for x in client.get("/applications", headers=b).json()}
    assert apps_a and apps_b and not apps_a & apps_b

    pa, pb = client.get("/portfolio", headers=a).json(), client.get("/portfolio", headers=b).json()
    assert pa["kpis"]["accounts"] == 140 and pb["kpis"]["accounts"] == 20
    assert not {x["factory_id"] for x in pa["accounts"]} & {x["factory_id"] for x in pb["accounts"]}

    alerts_a = {x["id"] for x in client.get("/alerts?status=ALL", headers=a).json()}
    alerts_b = {x["id"] for x in client.get("/alerts?status=ALL", headers=b).json()}
    assert not alerts_a & alerts_b
    assert {u["username"] for u in client.get("/staff", headers=b).json()} == {"rm2", "co2"}


def test_bank_b_cannot_reach_bank_a_records_by_id(client):
    a, b, co_b = login(client, "rm1"), login(client, "rm2"), login(client, "co2")
    hero = hero_app_id(client, a)
    assert client.post(f"/applications/{hero}/consent", headers=a).status_code == 200

    # Reads and writes on another bank's application behave as if it does not exist.
    assert client.get(f"/applications/{hero}", headers=b).status_code == 404
    assert client.get(f"/applications/{hero}/consent-ledger", headers=b).status_code == 404
    assert client.post(f"/applications/{hero}/score", headers=b).status_code == 404
    assert client.delete(f"/applications/{hero}/consent", headers=b).status_code == 404
    assert client.post("/score/simulate", headers=b, json={"application_id": hero, "adjustments": {}}).status_code == 404
    body = {"decision": "APPROVED", "comment": "cross-tenant attempt"}
    assert client.post(f"/applications/{hero}/decision", headers=co_b, json=body).status_code == 404

    alert_a = client.get("/alerts?status=ALL", headers=a).json()[0]["id"]
    assert client.post(f"/alerts/{alert_a}/action", headers=b, json={"action": "call"}).status_code == 404
    r = client.post("/alerts/bulk", headers=b, json={"ids": [alert_a], "action": "acknowledge"}).json()
    assert r == {"updated": 0, "skipped": 1}
    assert client.post("/alerts/bulk", headers=b, json={"ids": [alert_a], "action": "assign", "owner": "rm1"}).status_code == 422

    with SessionLocal() as db:  # nothing changed in bank A
        assert db.get(Application, hero).state == "CONSENTED"
        untouched = db.get(Alert, alert_a)
        assert untouched.status == "OPEN" and untouched.acknowledged_by is None and untouched.owner is None


def test_governance_views_are_tenant_scoped(client):
    risk_a, risk_b = login(client, "risk1"), login(client, "risk2")
    users_a = {r["user"] for r in client.get("/audit?limit=2000", headers=risk_a).json()}
    users_b = {r["user"] for r in client.get("/audit?limit=2000", headers=risk_b).json()}
    assert "rm1" in users_a and "rm2" not in users_a
    assert "rm2" in users_b and not users_b & {"rm1", "co1", "risk1", "sharma"}
    ledger_b = client.get("/consent-ledger?limit=2000", headers=risk_b).json()
    assert ledger_b["consents"]["ACTIVE"] == 20
    usage_a = client.get("/ai-usage?limit=2000", headers=risk_a).json()["calls"]
    usage_b = client.get("/ai-usage?limit=2000", headers=risk_b).json()["calls"]
    assert usage_a and usage_b and not {c["id"] for c in usage_a} & {c["id"] for c in usage_b}


def test_token_for_another_tenant_is_rejected(client):
    """A token whose tenant claim does not match the user's bank cannot be used."""
    import jwt

    from core.settings import get_settings

    token = client.post("/auth/login", json={"username": "rm1", "password": "demo123"}).json()
    assert token["tenant_id"] == "bank-a" and token["tenant_name"] == "Sample Bank Ltd"
    claims = jwt.decode(token["access_token"], get_settings().jwt_secret, algorithms=["HS256"])
    assert claims["tid"] == "bank-a"
    forged = jwt.encode({**claims, "tid": "bank-b"}, get_settings().jwt_secret, algorithm="HS256")
    assert client.get("/portfolio", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    no_tenant = jwt.encode({k: v for k, v in claims.items() if k != "tid"}, get_settings().jwt_secret, algorithm="HS256")
    assert client.get("/portfolio", headers={"Authorization": f"Bearer {no_tenant}"}).status_code == 401


def test_session_layer_filters_stamps_and_fails_closed(client):
    with SessionLocal() as db:
        total = db.query(Application).count()
        bind_tenant(db, "bank-b")
        mine = db.query(Application).all()
        assert 0 < len(mine) < total and {a.tenant_id for a in mine} == {"bank-b"}

        # Primary-key lookups and bulk statements are filtered too.
        with SessionLocal() as other:
            bind_tenant(other, "bank-a")
            foreign_id = other.query(Application.id).first()[0]
        assert db.get(Application, foreign_id) is None
        assert db.query(Alert).filter(Alert.application_id == foreign_id).update({"owner": "rm2"}) == 0
        assert db.query(Alert).filter(Alert.application_id == foreign_id).delete() == 0
        db.rollback()

        # New rows take the session's tenant; a row for another bank is refused.
        row = AuditLog(user="rm2", role="rm", agent="test", tool="t", action="a")
        db.add(row)
        db.flush()
        assert row.tenant_id == "bank-b"
        db.add(AuditLog(tenant_id="bank-a", user="x", role="rm", agent="test", tool="t", action="a"))
        with pytest.raises(TenantIsolationError):
            db.flush()
        db.rollback()

    with SessionLocal() as db:  # a request session before authentication
        db.info[ENFORCE_KEY] = True
        assert db.query(Tenant).count() == 2  # non-tenant tables are fine
        with pytest.raises(TenantIsolationError):
            db.query(User).all()
        with pytest.raises(TenantIsolationError):
            db.get(Application, 1)
        allow_cross_tenant(db)  # the explicit, greppable opt-out used by login
        assert db.query(User).count() >= 8
