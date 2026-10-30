"""Request/response models (Pydantic v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    display_name: str
    factory_id: str | None = None


class ApplicationCreate(BaseModel):
    factory_id: str = Field(examples=["UP-F0001"])
    requested_amount: float | None = Field(default=None, gt=0, description="INR; defaults to the profile's request")
    channel: Literal["rm", "app", "whatsapp"] = "rm"


class DecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str = Field(min_length=3, description="Mandatory justification by the credit officer")
    sanctioned_limit: float | None = Field(default=None, gt=0)


class AlertAction(BaseModel):
    action: Literal["call", "visit", "limit review", "restructure", "visit + limit review", "no action"]
    note: str = Field(default="", max_length=1000)


class ReviewRequest(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class Reason(BaseModel):
    feature: str
    pillar: str
    text: str
    value: float | None
    points: float
    direction: Literal["risk_up", "risk_down"]


class Pillar(BaseModel):
    pillar: str
    label: str
    prior_weight: float
    points: float
    health: float


class ScoreResponse(BaseModel):
    factory_id: str
    month: int
    pd_12m: float
    score: int
    band: Literal["APPROVE", "WATCH", "HIGH_RISK"]
    reasons: list[Reason]
    pillars: list[Pillar]
    base_points: float
    ai_label: str
