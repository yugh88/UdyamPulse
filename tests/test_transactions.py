"""Unit-of-work guarantees: a request commits everything or nothing, reads do not write, and audit
rows are committed together with the change they describe."""

from datetime import timedelta

import pytest

from agents.base import sim_date
from agents.ews_agent import EarlyWarningAgent
from agents.providers.consent import MockAAConsentProvider
from api.audit import SYSTEM
from api.models.db import Application, AuditLog, Consent, ConsentEvent, DataSnapshot, SessionLocal
from api.tenancy import bind_tenant
from tests.conftest import hero_app_id, login


def _counts() -> tuple[int, int, int]:
    with SessionLocal() as db:
        return db.query(AuditLog).count(), db.query(ConsentEvent).count(), db.query(DataSnapshot).count()


def test_failed_scoring_leaves_nothing_behind(client, monkeypatch):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    before = _counts()

    from ml import scoring

    def boom(self, row, top_k=5):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(scoring.Scorer, "explain_row", boom)
    with pytest.raises(RuntimeError):
        client.post(f"/applications/{app_id}/score", headers=rm)

    assert _counts() == before, "the data pull, its ledger row and its audit rows must roll back with the failed score"
    with SessionLocal() as db:
        app = db.get(Application, app_id)
        assert app.state == "CONSENTED" and app.score is None


def test_viewing_the_msme_app_does_not_write(client):
    msme = login(client, "sharma")
    first = client.get("/msme/UP-F0001/readiness", headers=msme).json()  # may write the plan once per data month
    assert first["data_stale"] is False and first["plan"]["steps"]
    before = _counts()
    for _ in range(3):
        again = client.get("/msme/UP-F0001/readiness", headers=msme).json()
        client.get("/msme/UP-F0001/notifications", headers=msme)
        client.get("/msme/UP-F0001/my-data", headers=msme)
    assert again["plan"]["summary"] == first["plan"]["summary"]
    assert _counts() == before


def test_staff_reads_do_not_write(client):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    before = _counts()
    for path in ("/portfolio", "/alerts", "/applications", f"/applications/{app_id}", "/applications/stats",
                 "/portfolio/migration", "/sim/clock"):
        assert client.get(path, headers=rm).status_code == 200
    assert _counts() == before


def test_expired_consent_is_inactive_on_read_and_recorded_by_the_batch(client):
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        today = sim_date(db)
        c = db.query(Consent).filter_by(status="ACTIVE").first()
        c.expires_on = today - timedelta(days=1)
        db.commit()
        provider = MockAAConsentProvider(db)
        before = db.query(ConsentEvent).count()
        assert provider.active(c.application_id, today) is None  # inactive immediately...
        assert provider.summary(c.application_id, today)["status"] == "EXPIRED"
        db.rollback()
        assert db.query(ConsentEvent).count() == before  # ...without the read writing anything

        EarlyWarningAgent(db, SYSTEM).run()
        db.refresh(c)
        assert c.status == "EXPIRED"
        assert db.query(ConsentEvent).filter_by(consent_id=c.id, event="EXPIRED").count() == 1
