from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.audit import Actor, log_event
from api.auth import CurrentUser, create_token, get_current_user, verify_password
from api.models.db import User, get_db
from api.models.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter_by(username=body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    log_event(db, Actor(user.username, user.role), agent="api", tool="auth", action="login")
    return LoginResponse(access_token=create_token(user), role=user.role, display_name=user.display_name,
                         factory_id=user.factory_id)


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"username": user.username, "role": user.role, "factory_id": user.factory_id}
