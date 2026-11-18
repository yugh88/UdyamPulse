"""Tamper-evident audit trail: every bank's audit rows form a SHA-256 hash chain.

Each row stores `chain_seq` (1, 2, 3 ... per tenant), `prev_hash` (the previous row's hash, or 64 zeros) and
`row_hash` = SHA-256 over its canonical content plus `prev_hash`. Changing, deleting or reordering any row
breaks every hash after it, which `verify_chain` reports with the first broken sequence number.

Chaining happens right after the INSERT, inside the same transaction, so the audit entry, its place in the
chain and the business change commit or roll back together. On PostgreSQL a per-tenant advisory lock orders
concurrent writers; on SQLite the INSERT already holds the database write lock. PostgreSQL additionally has
a trigger that refuses UPDATE or DELETE of a row once chained (see migration 0007).

A chain proves integrity relative to its head. Publishing the head hash somewhere the database admin cannot
rewrite (Azure immutable Blob storage, a daily signed report) closes the gap of an attacker re-hashing the
whole chain; `head()` returns what to publish."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from api.models.db import AuditLog

GENESIS = "0" * 64
FIELDS = ("tenant_id", "ts", "user", "role", "agent", "tool", "action", "application_id", "inputs", "output_hash")


def _ts(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)  # SQLite returns naive UTC, PostgreSQL aware
    return value.isoformat(timespec="microseconds")


def canonical(row: dict, seq: int, prev: str) -> bytes:
    body = {k: row.get(k) for k in FIELDS}
    body["ts"] = _ts(body["ts"])
    body["seq"], body["prev"] = seq, prev
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def row_hash(row: dict, seq: int, prev: str) -> str:
    return hashlib.sha256(canonical(row, seq, prev)).hexdigest()


def _as_dict(entry: AuditLog) -> dict:
    return {k: getattr(entry, k) for k in FIELDS}


def _lock(session: Session, tenant: str) -> None:
    conn = session.connection()
    if conn.dialect.name == "postgresql":
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"audit-chain:{tenant}"})


def _head(session: Session, tenant: str) -> tuple[int, str]:
    row = session.connection().execute(
        select(AuditLog.chain_seq, AuditLog.row_hash)
        .where(AuditLog.tenant_id == tenant, AuditLog.chain_seq.is_not(None))
        .order_by(AuditLog.chain_seq.desc()).limit(1)).first()
    return (row[0], row[1]) if row else (0, GENESIS)


@event.listens_for(Session, "after_flush")
def _chain_new_rows(session: Session, _flush_context) -> None:
    fresh = sorted((o for o in session.new if isinstance(o, AuditLog) and o.chain_seq is None), key=lambda o: o.id)
    if not fresh:
        return
    by_tenant: dict[str, list[AuditLog]] = {}
    for entry in fresh:
        by_tenant.setdefault(entry.tenant_id, []).append(entry)
    conn = session.connection()
    for tenant in sorted(by_tenant):  # fixed order, so two writers never wait on each other's locks in reverse
        _lock(session, tenant)
        seq, prev = _head(session, tenant)
        for entry in by_tenant[tenant]:
            seq += 1
            digest = row_hash(_as_dict(entry), seq, prev)
            conn.execute(update(AuditLog.__table__).where(AuditLog.__table__.c.id == entry.id)
                         .values(chain_seq=seq, prev_hash=prev, row_hash=digest))
            set_committed_value(entry, "chain_seq", seq)
            set_committed_value(entry, "prev_hash", prev)
            set_committed_value(entry, "row_hash", digest)
            prev = digest


def verify_chain(db: Session, batch: int = 2000) -> dict:
    """Walk the caller's chain (the session must be bound to one tenant) and recompute every hash."""
    expected_seq, prev, rows = 1, GENESIS, 0
    unchained = db.query(AuditLog).filter(AuditLog.chain_seq.is_(None)).count()
    last_seq = 0
    while True:
        chunk = (db.query(AuditLog).filter(AuditLog.chain_seq.is_not(None), AuditLog.chain_seq > last_seq)
                 .order_by(AuditLog.chain_seq).limit(batch).all())
        if not chunk:
            break
        for entry in chunk:
            problem = None
            if entry.chain_seq != expected_seq:
                problem = f"missing entries before sequence {entry.chain_seq} (expected {expected_seq})"
            elif entry.prev_hash != prev:
                problem = "link to the previous entry does not match"
            elif row_hash(_as_dict(entry), entry.chain_seq, prev) != entry.row_hash:
                problem = "entry content was changed after it was written"
            if problem:
                return {"ok": False, "rows_checked": rows, "unchained_rows": unchained,
                        "first_break": {"seq": entry.chain_seq, "audit_id": entry.id, "reason": problem}}
            prev, expected_seq, rows = entry.row_hash, expected_seq + 1, rows + 1
            last_seq = entry.chain_seq
    ok = unchained == 0
    return {"ok": ok, "rows_checked": rows, "unchained_rows": unchained, "head_seq": last_seq, "head_hash": prev,
            "first_break": None if ok else {"seq": None, "audit_id": None,
                                            "reason": f"{unchained} entries are outside the chain"}}
