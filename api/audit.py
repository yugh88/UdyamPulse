"""Audit trail: every API action and agent tool call is written to `audit_log` with PII masked
and a SHA-256 hash of the output (so outputs are verifiable without storing them twice).

`log_event` only adds the row to the session. It never commits: the audit entry and the business
change it describes are committed together by the caller, or rolled back together."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from api.models.db import AuditLog
from core.pii import PII_KEYS, mask_pii  # noqa: F401  (re-exported)


@dataclass(frozen=True)
class Actor:
    username: str
    role: str
    factory_id: str | None = None
    tenant_id: str | None = None
    branch: str | None = None  # staff home branch, for attribute-based access checks


SYSTEM = Actor("system", "system")


def output_hash(output: Any) -> str:
    blob = json.dumps(output, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def log_event(
    db: Session,
    actor: Actor,
    *,
    agent: str,
    tool: str,
    action: str,
    inputs: dict | None = None,
    output: Any = None,
    application_id: int | None = None,
) -> AuditLog:
    entry = AuditLog(
        user=actor.username,
        role=actor.role,
        agent=agent,
        tool=tool,
        action=action,
        application_id=application_id,
        inputs=mask_pii(json.loads(json.dumps(inputs or {}, default=str))),
        output_hash=output_hash(output) if output is not None else None,
    )
    db.add(entry)
    return entry
