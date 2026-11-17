"""Hash-chained audit trail: verification, tamper detection, per-bank chains, concurrent writers."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from api.audit import Actor, log_event
from api.audit_chain import GENESIS
from api.models.db import AuditLog, SessionLocal, is_postgres
from api.tenancy import allow_cross_tenant, bind_tenant
from tests.conftest import login


def _verify(client, user="risk1") -> dict:
    r = client.post("/audit/verify", headers=login(client, user))
    assert r.status_code == 200, r.text
    return r.json()


def _write(tenant: str, n: int, tag: str) -> None:
    with SessionLocal() as db:
        bind_tenant(db, tenant)
        for i in range(n):
            log_event(db, Actor("tester", "system"), agent="test", tool="chain", action=f"{tag}-{i}")
            db.commit()


def test_fresh_chain_verifies_and_reports_its_head(client):
    out = _verify(client)
    assert out["ok"] is True and out["rows_checked"] > 0 and out["unchained_rows"] == 0
    assert len(out["head_hash"]) == 64 and out["head_seq"] == out["rows_checked"]


def test_each_bank_has_its_own_chain(client):
    a, b = _verify(client, "risk1"), _verify(client, "risk2")
    assert a["ok"] and b["ok"] and a["head_hash"] != b["head_hash"]
    with SessionLocal() as db:
        bind_tenant(db, "bank-b")
        first = db.query(AuditLog).order_by(AuditLog.chain_seq).first()
    assert first.chain_seq == 1 and first.prev_hash == GENESIS


def test_rolled_back_entries_leave_no_gap(client):
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        log_event(db, Actor("tester", "system"), agent="test", tool="chain", action="rolled-back")
        db.flush()
        db.rollback()
    _write("bank-a", 2, "after-rollback")
    assert _verify(client)["ok"] is True


def test_concurrent_writers_keep_one_unbroken_chain(client):
    threads = [threading.Thread(target=_write, args=("bank-a", 10, f"t{n}")) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out = _verify(client)
    assert out["ok"] is True, out
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        seqs = [s for (s,) in db.query(AuditLog.chain_seq).order_by(AuditLog.chain_seq)]
    assert seqs == list(range(1, len(seqs) + 1))


def _tamper(sql: str) -> None:
    with SessionLocal() as db:
        allow_cross_tenant(db)
        db.execute(text(sql))
        db.commit()


@pytest.mark.skipif(is_postgres(), reason="PostgreSQL refuses the edit outright (next test)")
def test_an_edited_entry_is_detected(client):
    _write("bank-a", 3, "victim")
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        target = db.query(AuditLog).filter_by(action="victim-1").one()
    _tamper(f"UPDATE audit_log SET action = 'nothing-to-see' WHERE id = {target.id}")
    out = _verify(client)
    assert out["ok"] is False
    assert out["first_break"]["seq"] == target.chain_seq and "changed" in out["first_break"]["reason"]


@pytest.mark.skipif(is_postgres(), reason="PostgreSQL refuses the delete outright (next test)")
def test_a_deleted_entry_is_detected(client):
    from api import seed

    seed.main()  # undo the previous test's tampering
    _write("bank-a", 3, "gap")
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        target = db.query(AuditLog).filter_by(action="gap-1").one()
    _tamper(f"DELETE FROM audit_log WHERE id = {target.id}")
    out = _verify(client)
    assert out["ok"] is False and "missing" in out["first_break"]["reason"]
    seed.main()


@pytest.mark.skipif(not is_postgres(), reason="the append-only trigger is PostgreSQL only")
def test_postgres_refuses_to_change_or_delete_chained_entries(client):
    _write("bank-a", 1, "locked")
    with SessionLocal() as db:
        bind_tenant(db, "bank-a")
        target = db.query(AuditLog).filter_by(action="locked-0").one().id
    with pytest.raises(DBAPIError, match="cannot be changed"):
        _tamper(f"UPDATE audit_log SET action = 'x' WHERE id = {target}")
    with pytest.raises(DBAPIError, match="append-only"):
        _tamper(f"DELETE FROM audit_log WHERE id = {target}")
    assert _verify(client)["ok"] is True


def test_verify_is_risk_only(client):
    assert client.post("/audit/verify", headers=login(client, "rm1")).status_code == 403
