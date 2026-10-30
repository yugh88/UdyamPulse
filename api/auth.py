"""Simple JWT auth with roles (Microsoft Entra ID in production)."""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.audit import Actor
from api.models.db import User, get_db
from core.settings import get_settings

ROLES = ("rm", "credit_officer", "risk", "msme")
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def create_token(user: User) -> str:
    s = get_settings()
    payload = {
        "sub": user.username,
        "role": user.role,
        "factory_id": user.factory_id,
        "exp": datetime.now(UTC) + timedelta(minutes=s.jwt_ttl_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


CurrentUser = Actor


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    user = db.query(User).filter_by(username=payload["sub"]).one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return CurrentUser(user.username, user.role, user.factory_id)


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
