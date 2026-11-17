"""OLTP schema (SQLite locally, Azure Database for PostgreSQL in prod)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from functools import lru_cache

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from api.crypto import EncryptedJSON, EncryptedText
from api.tenancy import ENFORCE_KEY, TenantScoped
from core.settings import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """A bank using the platform. Every business row belongs to exactly one tenant."""

    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))


class User(TenantScoped, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(EncryptedText)  # personal data: encrypted at rest
    role: Mapped[str] = mapped_column(String(32))  # rm | credit_officer | risk | msme
    password_hash: Mapped[str] = mapped_column(String(256))
    factory_id: Mapped[str | None] = mapped_column(String(16), nullable=True)  # msme users only
    # Clusters this staff member covers, comma separated, or "*" for a zonal hub (api/authz.py)
    branch: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RefreshToken(TenantScoped, Base):
    """One rotating refresh token. Only its SHA-256 is stored. Every refresh marks the old token used and issues
    a new one in the same family; presenting a used token again means it was stolen, so the family is revoked."""

    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Application(TenantScoped, Base):
    __tablename__ = "applications"
    __table_args__ = (Index("ix_applications_tenant_state", "tenant_id", "state"),
                      Index("ix_applications_tenant_factory", "tenant_id", "factory_id"),
                      Index("ix_applications_tenant_cluster", "tenant_id", "cluster"))
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    cluster: Mapped[str | None] = mapped_column(String(32), nullable=True)  # factory's cluster: branch scope key
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
    decision_comment: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # free text: encrypted
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kfs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sanctioned_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    disbursement_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    disbursed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_ews_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_requested: Mapped[bool] = mapped_column(default=False)
    review_note: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    plan_cache: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # advisor plan for one data month
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


@event.listens_for(Application, "before_insert")
def _stamp_cluster(_mapper, _conn, app: Application) -> None:
    """Every application records its factory's cluster, which branch scope is checked against (api/authz.py)."""
    if app.cluster is None:
        from agents.providers.lake import get_lake

        try:
            app.cluster = get_lake().profile(app.factory_id)["cluster"]
        except (KeyError, FileNotFoundError):
            app.cluster = None


class Consent(TenantScoped, Base):
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


class ConsentEvent(TenantScoped, Base):
    """Append-only consent ledger (DPDP): grant, data pulls, revocation, deletion jobs."""

    __tablename__ = "consent_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    consent_id: Mapped[str] = mapped_column(String(40), index=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    event: Mapped[str] = mapped_column(String(32))  # GRANTED | DATA_PULL | PULL_BLOCKED | REVOKED | DELETION_JOB
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor: Mapped[str] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataSnapshot(TenantScoped, Base):
    """Pulled consented data held for an application. Deleted by the revocation deletion job."""

    __tablename__ = "data_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    upto_month: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(EncryptedJSON)  # consented financial data: encrypted at rest
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(TenantScoped, Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_tenant_status_severity", "tenant_id", "status", "severity"),)
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
    action_note: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    actioned_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)  # set when the action is logged
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)  # staff user responsible
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raised_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(TenantScoped, Base):
    """WhatsApp-style messages shown in the MSME app (mock channel)."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="whatsapp")
    text: Mapped[str] = mapped_column(Text)
    text_hi: Mapped[str | None] = mapped_column(Text, nullable=True)
    sim_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(TenantScoped, Base):
    """Append-only, hash-chained per tenant (api/audit_chain.py)."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_tenant_id_id", "tenant_id", "id"),
                      Index("ux_audit_log_tenant_chain_seq", "tenant_id", "chain_seq", unique=True))
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
    chain_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AiUsage(TenantScoped, Base):
    """One row per LLM-writer call: which prompt template, which provider, how long, roughly how big."""

    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    agent: Mapped[str] = mapped_column(String(48))
    template_id: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))  # template (local) | azure_openai | openai
    latency_ms: Mapped[float] = mapped_column(Float)
    tokens_est: Mapped[int] = mapped_column(Integer)  # estimate: characters / 4
    fallback: Mapped[bool] = mapped_column(default=False)  # provider failed or was rejected by the number guard
    # template | ok | cached | timeout | error | guard_rejected | breaker_open | busy (agents/providers/llm.py)
    outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    user: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class PlanProgress(TenantScoped, Base):
    """Steps of the 90-day plan that the MSME owner has ticked off."""

    __tablename__ = "plan_progress"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(16), index=True)
    step_key: Mapped[str] = mapped_column(String(64))
    done_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountScore(TenantScoped, Base):
    """Serving table: one row per monitored account per month (score, band, PD), written by the batch.
    The portfolio screens read this with indexed SQL instead of scanning the lake in memory.

    It grows by (accounts x months), so on PostgreSQL it is RANGE-partitioned by `month_date`
    (one partition per month, see migration 0002): old months can be detached or archived without
    touching current data, and month filters prune to a single partition."""

    __tablename__ = "account_scores"
    __table_args__ = (Index("ix_account_scores_tenant_month", "tenant_id", "month"),)
    tenant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    factory_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    month_date: Mapped[date] = mapped_column(Date, primary_key=True)  # first day of the data month
    month: Mapped[int] = mapped_column(Integer)  # panel month index
    application_id: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    band: Mapped[str] = mapped_column(String(16))
    pd_12m: Mapped[float] = mapped_column(Float)


class Job(TenantScoped, Base):
    """Background job (scoring, memo, early-warning batch). Clients follow it via SSE or polling.

    queued → running → succeeded, or running → failed (a retry is scheduled) → … → dead (retries exhausted)."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_tenant_updated", "tenant_id", "updated_at"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    message: Mapped[str | None] = mapped_column(String(256), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OutboxEvent(TenantScoped, Base):
    """Transactional outbox: written in the same transaction as the state change it announces, then
    published by the relay (`worker/relay.py`). No event is lost if the process dies after the commit,
    and none is published for a change that rolled back."""

    __tablename__ = "outbox"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class BatchRun(Base):
    """One nightly batch over the lake (platform-level operational data, not a bank's business data)."""

    __tablename__ = "batch_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    month: Mapped[int] = mapped_column(Integer)
    shards: Mapped[int] = mapped_column(Integer)
    chunk_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | succeeded | failed
    total_accounts: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BatchChunk(Base):
    """Checkpoint: a chunk is recorded only after its output file is fully written. A resumed run skips it."""

    __tablename__ = "batch_chunks"
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("batch_runs.id"), primary_key=True)
    chunk_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    shard: Mapped[int] = mapped_column(Integer)
    accounts: Mapped[int] = mapped_column(Integer)
    alerts: Mapped[int] = mapped_column(Integer)
    seconds: Mapped[float] = mapped_column(Float)
    worker: Mapped[str] = mapped_column(String(64))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    if not s.db_url.startswith("sqlite"):
        return create_engine(s.db_url, pool_size=10, max_overflow=20, pool_pre_ping=True)
    engine = create_engine(s.db_url, connect_args={"check_same_thread": False, "timeout": 15})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(conn, _record) -> None:  # the lite demo runs a worker thread beside the API
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.close()

    return engine


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def SessionLocal() -> Session:
    return _session_factory()()


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


def init_db() -> None:
    """SQLite (lite demo): create tables directly. PostgreSQL: run the Alembic migrations, which also
    create the monthly partitions and the row-level security policies."""
    if is_postgres():
        migrate()
    else:
        Base.metadata.create_all(get_engine())


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    from core.settings import ROOT

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")


def reset_db() -> None:
    """Empty every table (used by the demo seed). Keeps the PostgreSQL schema, partitions and policies."""
    engine = get_engine()
    if is_postgres():
        migrate()
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    db.info[ENFORCE_KEY] = True  # request sessions are fail-closed until the tenant is bound from the JWT
    try:
        yield db
    except Exception:
        db.rollback()  # a failed request leaves nothing half-written
        raise
    finally:
        db.close()
