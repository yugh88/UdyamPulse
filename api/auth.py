"""Authentication: argon2id passwords, short-lived JWT access tokens, rotating refresh tokens.

- Passwords are hashed with argon2id. Legacy PBKDF2 hashes still verify and are upgraded at the next login.
- Access tokens live `UP_JWT_TTL_MINUTES` (15 by default) and are kept in browser memory only.
- The refresh token is an httpOnly, SameSite=Strict cookie. Each use rotates it; reusing an already rotated
  token (outside a short grace window for two tabs refreshing at once) revokes the whole token family.

Microsoft Entra ID replaces the password step in production; the token handling stays the same."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.audit import Actor
from api.changes import set_actor
from api.models.db import RefreshToken, User, get_db, utcnow
from api.tenancy import bind_tenant
from core.settings import get_settings

ROLES = ("rm", "credit_officer", "risk", "msme")
REFRESH_COOKIE = "up_refresh"
REUSE_GRACE = timedelta(seconds=15)  # two tabs refreshing together share one cookie jar
_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _hasher() -> PasswordHasher:
    s = get_settings()
    return PasswordHasher(time_cost=s.argon2_time_cost, memory_cost=s.argon2_memory_kib,
                          parallelism=s.argon2_parallelism)


def hash_password(password: str) -> str:
    return _hasher().hash(password)


def _verify_pbkdf2(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def verify_password(password: str, stored: str) -> bool:
    if not stored.startswith("$argon2"):
        try:
            return _verify_pbkdf2(password, stored)
        except ValueError:
            return False
    try:
        return _hasher().verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    return not stored.startswith("$argon2") or _hasher().check_needs_rehash(stored)


# A real hash to compare against when the username does not exist, so timing does not reveal valid usernames.
@lru_cache
def dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def create_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user.username,
        "role": user.role,
        "factory_id": user.factory_id,
        "tid": user.tenant_id,
        "typ": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_ttl_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


# ---------- refresh tokens ----------

def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def issue_refresh(db: Session, user: User, family_id: str | None = None) -> tuple[RefreshToken, str]:
    """Add a new refresh token row to the session. Returns the row and the cookie value."""
    secret = secrets.token_urlsafe(32)
    row = RefreshToken(id=uuid.uuid4().hex, family_id=family_id or uuid.uuid4().hex, username=user.username,
                       token_hash=_digest(secret), tenant_id=user.tenant_id,
                       expires_at=utcnow() + timedelta(hours=get_settings().refresh_ttl_hours))
    db.add(row)
    return row, f"{row.id}.{secret}"


class RefreshRejected(Exception):
    def __init__(self, code: str, detail: str, row: RefreshToken | None = None) -> None:
        super().__init__(detail)
        self.code, self.detail, self.row = code, detail, row


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)  # SQLite returns naive datetimes


def check_refresh(db: Session, cookie: str | None) -> RefreshToken:
    """The refresh token behind `cookie`, or `RefreshRejected`. Caller must allow cross-tenant reads."""
    if not cookie or "." not in cookie:
        raise RefreshRejected("refresh_missing", "No refresh token")
    token_id, secret = cookie.split(".", 1)
    row = db.get(RefreshToken, token_id[:32])
    if row is None or not hmac.compare_digest(row.token_hash, _digest(secret)):
        raise RefreshRejected("refresh_invalid", "Invalid refresh token")
    now = utcnow()
    if row.revoked_at is not None:
        raise RefreshRejected("refresh_revoked", "Session ended. Sign in again.", row)
    if _aware(row.expires_at) <= now:
        raise RefreshRejected("refresh_expired", "Session expired. Sign in again.", row)
    if row.used_at is not None:
        if now - _aware(row.used_at) <= REUSE_GRACE:
            raise RefreshRejected("refresh_superseded", "Token already rotated by another tab; retry", row)
        raise RefreshRejected("refresh_reused", "Refresh token reuse detected. All sessions in this family ended.", row)
    return row


def revoke_family(db: Session, family_id: str) -> int:
    return db.query(RefreshToken).filter(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)) \
        .update({"revoked_at": utcnow()}, synchronize_session=False)


def set_refresh_cookie(response: Response, value: str) -> None:
    s = get_settings()
    response.set_cookie(REFRESH_COOKIE, value, max_age=s.refresh_ttl_hours * 3600, httponly=True,
                        secure=s.cookie_secure, samesite="strict", path="/")


def clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(REFRESH_COOKIE, path="/", httponly=True, secure=s.cookie_secure, samesite="strict")


# ---------- request authentication ----------

CurrentUser = Actor


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"],
                             options={"require": ["exp", "sub", "tid"]})
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if payload.get("typ", "access") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    # From here on, every query in this request is limited to the caller's bank.
    bind_tenant(db, payload["tid"])
    set_actor(db, payload["sub"])  # change events in this request are attributed to the signed-in user
    user = db.query(User).filter_by(username=payload["sub"]).one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return CurrentUser(user.username, user.role, user.factory_id, user.tenant_id, user.branch)


def require_roles(*roles: str) -> Callable[..., CurrentUser]:
    def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{user.role}' may not perform this action")
        return user

    return dep


def ensure_factory_access(user: CurrentUser, factory_id: str) -> None:
    """MSME users may only see their own factory."""
    if user.role == "msme" and user.factory_id != factory_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MSME users can only access their own factory")
