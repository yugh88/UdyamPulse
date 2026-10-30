"""OLTP schema (SQLite locally, Azure Database for PostgreSQL in prod)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from functools import lru_cache

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from core.settings import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))  # rm | credit_officer | risk | msme
    password_hash: Mapped[str] = mapped_column(String(256))
    factory_id: Mapped[str | None] = mapped_column(String(16), nullable=True)  # msme users only


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    state: Mapped[str] = mapped_column(String(24), default="APPLIED")
    channel: Mapped[str] = mapped_column(String(16), default="rm")
    requested_amount: Mapped[float] = mapped_column(Float)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pd_12m: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_checks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    memo: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    memo_pdf: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recommended_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    pricing_band: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # APPROVED | REJECTED
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kfs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sanctioned_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    disbursement_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    disbursed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_ews_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_requested: Mapped[bool] = mapped_column(default=False)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Consent(Base):
    """Account Aggregator style consent artefact (one per application)."""

    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    purpose: Mapped[str] = mapped_column(String(256))
    fi_types: Mapped[list] = mapped_column(JSON)
    data_from: Mapped[date] = mapped_column(Date)
    data_to: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date] = mapped_column(Date)
    frequency: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")  # ACTIVE | REVOKED | EXPIRED
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentEvent(Base):
    """Append-only consent ledger (DPDP): grant, data pulls, revocation, deletion jobs."""

    __tablename__ = "consent_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    consent_id: Mapped[str] = mapped_column(String(40), index=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    event: Mapped[str] = mapped_column(String(32))  # GRANTED | DATA_PULL | PULL_BLOCKED | REVOKED | DELETION_JOB
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor: Mapped[str] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataSnapshot(Base):
    """Pulled consented data held for an application. Deleted by the revocation deletion job."""

    __tablename__ = "data_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    upto_month: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    month: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(8))
    rules: Mapped[list] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    next_best_action: Mapped[str] = mapped_column(String(64))
    briefing: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN | ACTIONED
    action_taken: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actioned_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raised_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """WhatsApp-style messages shown in the MSME app (mock channel)."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="whatsapp")
    text: Mapped[str] = mapped_column(Text)
    sim_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))
    agent: Mapped[str] = mapped_column(String(48))
    tool: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SimClock(Base):
    __tablename__ = "sim_clock"
    id: Mapped[int] = mapped_column(primary_key=True)
    current_date: Mapped[date] = mapped_column(Date)


@lru_cache
def get_engine():
    s = get_settings()
    if s.db_url.startswith("sqlite:///"):
        from pathlib import Path

        Path(s.db_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(s.db_url, connect_args={"check_same_thread": False} if s.db_url.startswith("sqlite") else {})


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def SessionLocal() -> Session:
    return _session_factory()()


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
