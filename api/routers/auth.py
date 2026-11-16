from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.audit import Actor, log_event
from api.auth import CurrentUser, create_token, get_current_user, verify_password
from api.models.db import Tenant, User, get_db
from api.models.schemas import LoginRequest, LoginResponse
from api.tenancy import allow_cross_tenant, bind_tenant

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    allow_cross_tenant(db)  # the username decides the bank, so this one lookup spans tenants
    user = db.query(User).filter_by(username=body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    bind_tenant(db, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    log_event(db, Actor(user.username, user.role), agent="api", tool="auth", action="login")
    db.commit()
    return LoginResponse(access_token=create_token(user), role=user.role, display_name=user.display_name,
                         factory_id=user.factory_id, tenant_id=user.tenant_id,
                         tenant_name=tenant.name if tenant else user.tenant_id)


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"username": user.username, "role": user.role, "factory_id": user.factory_id, "tenant_id": user.tenant_id}
