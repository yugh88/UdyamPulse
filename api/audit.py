"""Audit trail: every API action and agent tool call is written to `audit_log` with PII masked
and a SHA-256 hash of the output (so outputs are verifiable without storing them twice)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from api.models.db import AuditLog

PII_KEYS = {"name", "display_name", "phone", "mobile", "email", "pan", "aadhaar", "gstin", "account_number", "address"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?<!\d)(\+91[\s-]?)?[6-9]\d{9}(?!\d)")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


@dataclass(frozen=True)
class Actor:
    username: str
    role: str
    factory_id: str | None = None


SYSTEM = Actor("system", "system")


def _mask_str(value: str) -> str:
    value = _EMAIL.sub("***@***", value)
    value = _PHONE.sub("**********", value)
    return _PAN.sub("*****####*", value)


def mask_pii(obj: Any) -> Any:
    """Recursively mask PII-bearing keys and patterns before anything is logged."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.lower() in PII_KEYS and isinstance(v, str):
                out[k] = (v[:2] + "***") if v else v
            else:
                out[k] = mask_pii(v)
        return out
    if isinstance(obj, list):
        return [mask_pii(v) for v in obj]
    if isinstance(obj, str):
        return _mask_str(obj)
    return obj


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
    commit: bool = True,
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
    if commit:
        db.commit()
    return entry
