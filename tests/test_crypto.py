"""Field-level encryption: ciphertext at rest, plaintext through the ORM, key rotation."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import text

from api import crypto
from api.models.db import Alert, DataSnapshot, SessionLocal, User
from api.tenancy import allow_cross_tenant
from core.settings import get_settings
from tests.conftest import hero_app_id, login


def _raw(sql: str, **params):
    with SessionLocal() as db:
        allow_cross_tenant(db)
        return db.execute(text(sql), params).scalar_one()


def test_personal_fields_are_ciphertext_at_rest_and_plaintext_through_the_api(client):
    raw = _raw("SELECT display_name FROM users WHERE username = 'sharma'")
    assert raw.startswith(crypto.PREFIX) and "Sharma" not in raw
    r = client.post("/auth/login", json={"username": "sharma", "password": "demo123"})
    assert r.json()["display_name"] == "Suresh Sharma"


def test_consented_data_snapshot_is_encrypted(client):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    assert client.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
    assert client.post(f"/applications/{app_id}/score", headers=rm).status_code == 200
    raw = _raw("SELECT payload FROM data_snapshots WHERE application_id = :a ORDER BY id DESC LIMIT 1", a=app_id)
    assert raw.startswith(crypto.PREFIX)
    with SessionLocal() as db:
        allow_cross_tenant(db)
        snap = db.query(DataSnapshot).filter_by(application_id=app_id).order_by(DataSnapshot.id.desc()).first()
        assert isinstance(snap.payload, dict) and snap.payload


def test_free_text_notes_are_encrypted(client):
    with SessionLocal() as db:
        allow_cross_tenant(db)
        alert = db.query(Alert).first()
        if alert is None:
            pytest.skip("no alert seeded")
        alert.action_note = "Called promoter on 9876543210 about delayed GST filing"
        db.commit()
        alert_id = alert.id
    raw = _raw("SELECT action_note FROM alerts WHERE id = :i", i=alert_id)
    assert raw.startswith(crypto.PREFIX) and "9876543210" not in raw
    with SessionLocal() as db:
        allow_cross_tenant(db)
        assert db.get(Alert, alert_id).action_note.startswith("Called promoter")


def test_legacy_plaintext_is_still_readable():
    assert crypto.decrypt("written before encryption") == "written before encryption"


def test_key_rotation_keeps_old_values_readable_then_reencrypts(client, monkeypatch):
    old_key, new_key = crypto.DEMO_KEY, crypto.new_key()
    before = _raw("SELECT display_name FROM users WHERE username = 'co1'")
    # Newest key first, old key still listed: old ciphertext decrypts, new writes use the new key.
    s = replace(get_settings(), field_keys_raw=f"{new_key},{old_key}")
    monkeypatch.setattr(crypto, "get_settings", lambda: s)
    with SessionLocal() as db:
        allow_cross_tenant(db)
        assert db.query(User).filter_by(username="co1").one().display_name == "Priya Malhotra"
    counts = crypto.rotate()
    assert counts["users.display_name"] >= 4
    after = _raw("SELECT display_name FROM users WHERE username = 'co1'")
    assert after != before and after.startswith(crypto.PREFIX)
    # With only the new key the rotated value still decrypts; the old key is no longer needed.
    only_new = replace(get_settings(), field_keys_raw=new_key)
    monkeypatch.setattr(crypto, "get_settings", lambda: only_new)
    assert crypto.decrypt(after) == "Priya Malhotra"
    with pytest.raises(ValueError, match="cannot be decrypted"):
        crypto.decrypt(before)
    # Put the demo key back for the rest of the suite.
    monkeypatch.setattr(crypto, "get_settings", lambda: replace(get_settings(), field_keys_raw=f"{old_key},{new_key}"))
    crypto.rotate()
