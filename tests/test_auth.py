"""Sign-in hardening: argon2id, short-lived access tokens, rotating refresh cookies with reuse detection."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from api import auth
from api.models.db import AuditLog, RefreshToken, SessionLocal, User
from api.tenancy import allow_cross_tenant
from core.settings import get_settings

COOKIE = auth.REFRESH_COOKIE


def _login(client, username="rm1", password="demo123"):
    client.cookies.clear()
    return client.post("/auth/login", json={"username": username, "password": password})


def _refresh(client, cookie: str | None):
    client.cookies.clear()
    if cookie:
        client.cookies.set(COOKIE, cookie)
    return client.post("/auth/refresh")


def test_login_sets_httponly_strict_refresh_cookie_and_short_access_token(client):
    r = _login(client)
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"]
    assert f"{COOKIE}=" in set_cookie and "HttpOnly" in set_cookie and "SameSite=strict" in set_cookie
    assert "Path=/" in set_cookie
    claims = jwt.decode(r.json()["access_token"], options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == get_settings().jwt_ttl_minutes * 60 == 15 * 60
    assert claims["typ"] == "access" and claims["jti"]


def test_passwords_are_argon2id(client):
    with SessionLocal() as db:
        allow_cross_tenant(db)
        stored = db.query(User).filter_by(username="co1").one().password_hash
    assert stored.startswith("$argon2id$")


def test_refresh_rotates_and_old_token_reuse_revokes_the_family(client, monkeypatch):
    first = _login(client).cookies[COOKIE]
    r = _refresh(client, first)
    assert r.status_code == 200 and r.json()["access_token"]
    second = r.cookies[COOKIE]
    assert second != first
    # Within the grace window a second tab replaying the old cookie is told to retry, nothing is revoked.
    r = _refresh(client, first)
    assert r.status_code == 401 and r.json()["code"] == "refresh_superseded"
    r = _refresh(client, second)
    assert r.status_code == 200  # still alive
    # Past the grace window the same replay is treated as theft: the whole family ends.
    third = r.cookies[COOKIE]
    monkeypatch.setattr(auth, "REUSE_GRACE", timedelta(0))
    r = _refresh(client, first)
    assert r.status_code == 401 and r.json()["code"] == "refresh_reused"
    assert _refresh(client, third).json()["code"] == "refresh_revoked"
    with SessionLocal() as db:
        allow_cross_tenant(db)
        assert db.query(AuditLog).filter_by(action="refresh_reuse_detected").count() >= 1


def test_logout_revokes_refresh_and_clears_cookie(client):
    cookie = _login(client).cookies[COOKIE]
    client.cookies.set(COOKIE, cookie)
    r = client.post("/auth/logout")
    assert r.status_code == 204 and f'{COOKIE}=""' in r.headers["set-cookie"]
    assert _refresh(client, cookie).json()["code"] == "refresh_revoked"


def test_refresh_rejects_missing_tampered_and_expired_tokens(client):
    assert _refresh(client, None).json()["code"] == "refresh_missing"
    cookie = _login(client).cookies[COOKIE]
    token_id, _secret = cookie.split(".", 1)
    assert _refresh(client, f"{token_id}.forged-secret").json()["code"] == "refresh_invalid"
    with SessionLocal() as db:
        allow_cross_tenant(db)
        db.get(RefreshToken, token_id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert _refresh(client, cookie).json()["code"] == "refresh_expired"


def test_only_the_hash_of_a_refresh_token_is_stored(client):
    cookie = _login(client).cookies[COOKIE]
    token_id, secret = cookie.split(".", 1)
    with SessionLocal() as db:
        allow_cross_tenant(db)
        row = db.get(RefreshToken, token_id)
    assert secret not in (row.token_hash or "") and row.token_hash == hashlib.sha256(secret.encode()).hexdigest()


def test_expired_or_wrong_type_access_token_is_rejected(client):
    s = get_settings()
    now = datetime.now(UTC)
    base = {"sub": "rm1", "role": "rm", "tid": "bank-a", "iat": now}
    expired = jwt.encode({**base, "exp": now - timedelta(seconds=5)}, s.jwt_secret, algorithm="HS256")
    wrong_type = jwt.encode({**base, "typ": "refresh", "exp": now + timedelta(minutes=5)}, s.jwt_secret, algorithm="HS256")
    no_tenant = jwt.encode({"sub": "rm1", "exp": now + timedelta(minutes=5)}, s.jwt_secret, algorithm="HS256")
    for token in (expired, wrong_type, no_tenant):
        assert client.get("/applications", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unknown_user_and_wrong_password_look_the_same(client):
    a = _login(client, "nobody-here", "demo123")
    b = _login(client, "rm1", "wrong-password")
    assert a.status_code == b.status_code == 401 and a.json()["detail"] == b.json()["detail"]
    assert "set-cookie" not in a.headers and "set-cookie" not in b.headers


def test_legacy_pbkdf2_hash_is_upgraded_at_login(client):
    salt = os.urandom(16)
    legacy = f"{salt.hex()}${hashlib.pbkdf2_hmac('sha256', b'demo123', salt, 120_000).hex()}"
    with SessionLocal() as db:
        allow_cross_tenant(db)
        db.query(User).filter_by(username="risk1").one().password_hash = legacy
        db.commit()
    assert _login(client, "risk1").status_code == 200
    with SessionLocal() as db:
        allow_cross_tenant(db)
        assert db.query(User).filter_by(username="risk1").one().password_hash.startswith("$argon2id$")


@pytest.mark.parametrize("path", ["/auth/login", "/auth/refresh"])
def test_auth_endpoints_are_never_replayed_by_idempotency(client, path):
    cookie = _login(client).cookies[COOKIE]
    headers = {"Idempotency-Key": "same-key-123", "Authorization": f"Bearer {_login(client).json()['access_token']}"}
    client.cookies.set(COOKIE, cookie)
    body = {"username": "rm1", "password": "demo123"} if path.endswith("login") else None
    first = client.post(path, json=body, headers=headers)
    client.cookies.set(COOKIE, first.cookies.get(COOKIE) or cookie)
    second = client.post(path, json=body, headers=headers)
    assert "idempotency-replayed" not in second.headers
    assert first.json()["access_token"] != second.json()["access_token"]
