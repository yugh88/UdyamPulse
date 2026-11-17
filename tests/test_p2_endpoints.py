"""Endpoints added for the rebuilt screens: KPIs, richer signals, what-if simulation, policy lookup,
alert ownership, band migration, governance logs, plan progress and the demo reset."""

from api.models.db import Application, AuditLog, ConsentEvent, DataSnapshot, SessionLocal
from tests.conftest import advance, hero_app_id, login


def _consented_hero(client) -> tuple[dict, int]:
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    return rm, app_id


def test_stats_and_detail_signals(client):
    rm, app_id = _consented_hero(client)
    stats = client.get("/applications/stats", headers=rm).json()
    assert stats["pending"] == 4 and stats["approval_rate"] is None  # no decisions made in the app yet

    d = client.get(f"/applications/{app_id}", headers=rm).json()
    assert len(d["signals"]) == 20 and {"eway_value", "avg_days_to_pay", "gst_filing_delay_days"} <= set(d["signals"][0])
    assert len(d["score_history"]) == 20 and d["score_history"][-1]["score"] == 723
    assert d["stress_start"] is None  # the hero is healthy at the start of the demo
    assert d["peers"]["cluster"] == "Ludhiana" and d["peers"]["rows"][0]["metric"] == "score"


def test_signals_hidden_without_consent(client):
    rm = login(client, "rm1")
    other = next(a["id"] for a in client.get("/applications", headers=rm).json() if a["factory_id"] != "UP-F0001")
    d = client.get(f"/applications/{other}", headers=rm).json()
    assert d["signals"] == [] and d["score_history"] == [] and d["peers"] is None
    r = client.post("/score/simulate", headers=rm, json={"application_id": other, "adjustments": {}})
    assert r.status_code == 403


def test_simulation_is_read_only_and_labelled(client):
    rm, app_id = _consented_hero(client)

    def counts():
        with SessionLocal() as db:
            a = db.get(Application, app_id)
            return (a.state, a.score, db.query(AuditLog).count(), db.query(ConsentEvent).count(),
                    db.query(DataSnapshot).count())

    before = counts()
    none = client.post("/score/simulate", headers=rm, json={"application_id": app_id, "adjustments": {}}).json()
    assert none["simulation"] is True and "not a score of record" in none["label"]
    assert none["delta"] == 0 and none["base"]["score"] == none["simulated"]["score"] == 723

    hit = client.post("/score/simulate", headers=rm,
                      json={"application_id": app_id, "adjustments": {"bounces_count": 2, "days_to_pay_days": 30}}).json()
    assert hit["delta"] < 0 and hit["simulated"]["score"] == hit["base"]["score"] + hit["delta"]
    assert len(hit["simulated"]["reasons"]) == 5
    assert counts() == before, "simulation must not write state, audit rows, ledger rows or snapshots"

    clipped = client.post("/score/simulate", headers=rm,
                          json={"application_id": app_id, "adjustments": {"dispatch_pct": 500}}).json()
    assert clipped["adjustments"]["dispatch_pct"] == 50
    bad = client.post("/score/simulate", headers=rm, json={"application_id": app_id, "adjustments": {"magic": 1}})
    assert bad.status_code == 422
    assert client.post("/score/simulate", headers=login(client, "sharma"),
                       json={"application_id": app_id, "adjustments": {}}).status_code == 403


def test_policy_clause_lookup(client):
    rm = login(client, "rm1")
    c = client.get("/policy/4.1", headers=rm).json()
    assert c["section"] == "4.1" and len(c["text"]) > 40
    assert client.get("/policy/99.9", headers=rm).status_code == 404
    levers = client.get("/score/levers", headers=rm).json()
    assert {lv["key"] for lv in levers["levers"]} >= {"dispatch_pct", "top_buyer_share_pp"}


def test_alert_bulk_assign_acknowledge_and_outcome(client):
    rm, risk = login(client, "rm1"), login(client, "risk1")
    alerts = client.get("/alerts", headers=rm).json()
    assert alerts and all(a["owner"] is None and a["days_open"] >= 0 and a["timeline"] for a in alerts)
    ids = [a["id"] for a in alerts[:3]]

    assert client.post("/alerts/bulk", headers=risk, json={"ids": ids, "action": "acknowledge"}).status_code == 403
    assert client.post("/alerts/bulk", headers=rm, json={"ids": ids, "action": "assign", "owner": "sharma"}).status_code == 422
    assert client.post("/alerts/bulk", headers=rm, json={"ids": ids, "action": "assign", "owner": "co1"}).json()["updated"] == 3
    assert client.post("/alerts/bulk", headers=rm, json={"ids": ids[:2], "action": "acknowledge"}).json()["updated"] == 2

    after = {a["id"]: a for a in client.get("/alerts", headers=rm).json()}
    assert all(after[i]["owner"] == "co1" for i in ids)
    assert after[ids[0]]["acknowledged_by"] == "rm1" and after[ids[2]]["acknowledged_by"] is None

    r = client.post(f"/alerts/{ids[0]}/action", headers=rm, json={"action": "call", "note": "Spoke to owner", "outcome": "monitoring"})
    assert r.status_code == 200
    done = next(a for a in client.get("/alerts?status=ALL", headers=rm).json() if a["id"] == ids[0])
    assert done["status"] == "ACTIONED" and done["outcome"] == "monitoring"
    # Actioned alerts are skipped by later bulk operations.
    assert client.post("/alerts/bulk", headers=rm, json={"ids": ids, "action": "acknowledge"}).json()["skipped"] == 1
    assert {u["username"] for u in client.get("/staff", headers=rm).json()} == {"rm1", "rm3", "co1"}


def test_band_migration_matrix_adds_up(client):
    rm = login(client, "rm1")
    m = client.get("/portfolio/migration", headers=rm).json()
    total = sum(m["matrix"][a][b] for a in m["bands"] for b in m["bands"])
    assert total == m["accounts"] > 0
    moved = sum(m["matrix"][a][b] for a in m["bands"] for b in m["bands"] if a != b)
    assert moved == len(m["movers"]) == m["upgrades"] + m["downgrades"]


def test_governance_logs_are_risk_only(client):
    rm, risk = login(client, "rm1"), login(client, "risk1")
    for path in ("/consent-ledger", "/ai-usage"):
        assert client.get(path, headers=rm).status_code == 403
    ledger = client.get("/consent-ledger", headers=risk).json()
    assert ledger["consents"]["ACTIVE"] > 0 and ledger["events"][0]["name"]
    usage = client.get("/ai-usage", headers=risk).json()
    assert usage["summary"]["calls"] > 0 and usage["summary"]["provider_in_use"] == "template"
    call = usage["calls"][0]
    assert call["template_id"] == "ews.briefing.v1" and call["location"] == "local" and call["tokens_est"] > 0


def test_plan_progress_persists(client):
    msme = login(client, "sharma")
    plan = client.get("/msme/UP-F0001/readiness", headers=msme).json()["plan"]
    key = plan["steps"][0]["key"]
    assert plan["steps_done"] == 0 and len({s["key"] for s in plan["steps"]}) == len(plan["steps"])
    assert client.put(f"/msme/UP-F0001/plan/steps/{key}", headers=msme, json={"done": True}).status_code == 200
    plan = client.get("/msme/UP-F0001/readiness", headers=msme).json()["plan"]
    assert plan["steps_done"] == 1 and plan["steps"][0]["done"] is True
    client.put(f"/msme/UP-F0001/plan/steps/{key}", headers=msme, json={"done": False})
    assert client.get("/msme/UP-F0001/readiness", headers=msme).json()["plan"]["steps_done"] == 0
    assert client.put(f"/msme/UP-F0044/plan/steps/{key}", headers=msme, json={"done": True}).status_code == 403


def test_demo_reset_restores_seed_state_quickly(client):
    rm = login(client, "rm1")
    advance(client, rm, 40)
    assert client.get("/sim/clock", headers=rm).json()["sim_date"] != "2026-06-30"
    r = client.post("/demo/reset").json()
    assert r["status"] == "reset" and r["took_ms"] < 3000
    rm = login(client, "rm1")
    assert client.get("/sim/clock", headers=rm).json()["sim_date"] == "2026-06-30"
    assert all(a["state"] == "APPLIED" for a in client.get("/applications", headers=rm).json())


def test_demo_reset_is_unavailable_outside_demo_mode(client, monkeypatch):
    from dataclasses import replace

    from api.routers import governance
    from core.settings import get_settings

    prod = replace(get_settings(), data_region="centralindia")
    monkeypatch.setattr(governance, "get_settings", lambda: prod)
    assert prod.demo_mode is False
    assert client.post("/demo/reset").status_code == 404


def test_every_feature_has_a_hindi_template():
    from ml.features import FEATURE_NAMES, PILLARS
    from ml.i18n_hi import PILLARS_HI, TEMPLATES_HI, describe_hi

    assert set(TEMPLATES_HI) == set(FEATURE_NAMES)
    assert all("{v}" in t for t in TEMPLATES_HI.values())
    assert set(PILLARS_HI) == set(PILLARS)
    assert describe_hi("bounces_12", 3.0) == "12 महीनों में 3 चेक/NACH बाउंस"
    assert describe_hi("days_to_pay_1", 72.0) == "खरीदार 72 दिन में भुगतान करते हैं"


def test_msme_content_is_available_in_hindi(client):
    rm, app_id = _consented_hero(client)
    msme = login(client, "sharma")
    r = client.get("/msme/UP-F0001/readiness", headers=msme).json()
    assert r["application_id"] == app_id
    assert all(x["text_hi"] for x in r["reasons"]) and all(p["label_hi"] for p in r["pillars"])
    assert all(s["action_hi"] and s["phase_hi"] for s in r["plan"]["steps"])
    notes = client.get("/msme/UP-F0001/notifications", headers=msme).json()
    assert notes and all(n["text_hi"] for n in notes)


def test_consent_status_is_reported_after_revocation(client):
    rm, app_id = _consented_hero(client)
    msme = login(client, "sharma")
    assert client.get(f"/applications/{app_id}", headers=rm).json()["consent"]["status"] == "ACTIVE"
    client.delete(f"/applications/{app_id}/consent", headers=msme)
    for view in (client.get(f"/applications/{app_id}", headers=rm).json(),
                 client.get("/msme/UP-F0001/readiness", headers=msme).json()):
        assert view["consent"]["active"] is False and view["consent"]["status"] == "REVOKED"
    other = next(a["id"] for a in client.get("/applications", headers=rm).json() if a["factory_id"] != "UP-F0001")
    assert client.get(f"/applications/{other}", headers=rm).json()["consent"] == {"active": False, "status": None, "revoked_at": None}
