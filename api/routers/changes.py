"""Mark items as seen, so their "Updated" / "New" markers clear for this user."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.changes import mark_seen
from api.models.db import get_db

router = APIRouter(tags=["changes"])


class SeenRequest(BaseModel):
    entity_type: Literal["application", "alert"]
    ids: list[str] = Field(default_factory=list, max_length=500, description="Items the user has just looked at")
    all: bool = Field(default=False, description="Mark every item of this type as seen")


@router.post("/seen")
def seen(body: SeenRequest, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> dict:
    marked = mark_seen(db, user, body.entity_type, ["*"] if body.all else [str(i) for i in body.ids])
    db.commit()
    return {"marked": marked, "entity_type": body.entity_type, "all": body.all}
