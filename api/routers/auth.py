from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.audit import Actor, log_event
from api.auth import (
    REFRESH_COOKIE,
    CurrentUser,
    RefreshRejected,
    check_refresh,
    clear_refresh_cookie,
    create_token,
    dummy_hash,
    get_current_user,
    hash_password,
    issue_refresh,
    needs_rehash,
    revoke_family,
    set_refresh_cookie,
    verify_password,
)
from api.models.db import Tenant, User, get_db, utcnow
from api.models.schemas import LoginRequest, LoginResponse
from api.problems import problem
from api.tenancy import allow_cross_tenant, bind_tenant
from core import metrics

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_body(db: Session, user: User) -> LoginResponse:
    tenant = db.get(Tenant, user.tenant_id)
    return LoginResponse(access_token=create_token(user), role=user.role, display_name=user.display_name,
                         factory_id=user.factory_id, tenant_id=user.tenant_id,
                         tenant_name=tenant.name if tenant else user.tenant_id)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    allow_cross_tenant(db)  # the username decides the bank, so this one lookup spans tenants
    user = db.query(User).filter_by(username=body.username).one_or_none()
    if user is None:
        verify_password(body.password, dummy_hash())  # same work as a real check: no username probing by timing
        metrics.AUTH_EVENTS.labels("login_failed").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    bind_tenant(db, user.tenant_id)
    actor = Actor(user.username, user.role)
    if not verify_password(body.password, user.password_hash):
        log_event(db, actor, agent="api", tool="auth", action="login_failed")
        db.commit()
        metrics.AUTH_EVENTS.labels("login_failed").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if needs_rehash(user.password_hash):  # legacy PBKDF2 or weaker argon2 parameters: upgrade in place
        user.password_hash = hash_password(body.password)
    _, cookie = issue_refresh(db, user)
    log_event(db, actor, agent="api", tool="auth", action="login")
    out = _session_body(db, user)
    db.commit()
    set_refresh_cookie(response, cookie)
    metrics.AUTH_EVENTS.labels("login").inc()
    return out


@router.post("/refresh", response_model=LoginResponse, responses={401: {"description": "Refresh token missing, "
             "expired, revoked or reused (problem+json `code` says which)"}})
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Swap the refresh cookie for a new access token and a new refresh cookie (rotation)."""
    allow_cross_tenant(db)  # the cookie names the token, and the token names the bank
    try:
        row = check_refresh(db, request.cookies.get(REFRESH_COOKIE))
    except RefreshRejected as rejected:
        if rejected.code == "refresh_reused" and rejected.row is not None:
            bind_tenant(db, rejected.row.tenant_id)
            revoke_family(db, rejected.row.family_id)
            log_event(db, Actor(rejected.row.username, "unknown"), agent="api", tool="auth",
                      action="refresh_reuse_detected", inputs={"family": rejected.row.family_id[:8]})
            db.commit()
        metrics.AUTH_EVENTS.labels(rejected.code).inc()
        err: JSONResponse = problem(request, 401, rejected.detail, code=rejected.code)
        if rejected.code != "refresh_superseded":  # another tab holds the newer cookie; keep it
            clear_refresh_cookie(err)
        return err
    bind_tenant(db, row.tenant_id)
    user = db.query(User).filter_by(username=row.username).one_or_none()
    if user is None:
        revoke_family(db, row.family_id)
        db.commit()
        err = problem(request, 401, "Account no longer exists", code="refresh_revoked")
        clear_refresh_cookie(err)
        return err
    new_row, cookie = issue_refresh(db, user, family_id=row.family_id)
    row.used_at, row.replaced_by = utcnow(), new_row.id
    out = _session_body(db, user)
    db.commit()
    set_refresh_cookie(response, cookie)
    metrics.AUTH_EVENTS.labels("refresh").inc()
    return out


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """End this browser's session: the refresh token family is revoked and the cookie cleared."""
    allow_cross_tenant(db)
    out = Response(status_code=204)
    try:
        row = check_refresh(db, request.cookies.get(REFRESH_COOKIE))
    except RefreshRejected as rejected:
        row = rejected.row if rejected.code in ("refresh_superseded", "refresh_reused") else None
    if row is not None:
        bind_tenant(db, row.tenant_id)
        revoke_family(db, row.family_id)
        log_event(db, Actor(row.username, "unknown"), agent="api", tool="auth", action="logout")
        db.commit()
        metrics.AUTH_EVENTS.labels("logout").inc()
    clear_refresh_cookie(out)
    return out


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"username": user.username, "role": user.role, "factory_id": user.factory_id, "tenant_id": user.tenant_id,
            "branch": user.branch}
