"""Response cache for portfolio aggregates, invalidated by events.

Each tenant has a version counter. Any committed change to applications, alerts, consents or account
scores bumps that tenant's version; a change to the simulated clock bumps a global version. Cache keys
include both versions, so a write makes old entries unreachable at once; the short TTL only bounds memory.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from api.kv import get_kv
from core.settings import get_settings

_TENANT_DIRTY, _GLOBAL_DIRTY = "cache_dirty_tenants", "cache_dirty_global"


def _watched() -> tuple[type, ...]:
    from api.models.db import AccountScore, Alert, Application, Consent

    return Application, Alert, Consent, AccountScore


@event.listens_for(Session, "before_flush")
def _collect(session: Session, _ctx, _instances) -> None:
    from api.models.db import SimClock

    watched = _watched()
    for obj in (*session.new, *session.dirty, *session.deleted):
        if isinstance(obj, watched) and getattr(obj, "tenant_id", None):
            session.info.setdefault(_TENANT_DIRTY, set()).add(obj.tenant_id)
        elif isinstance(obj, SimClock):
            session.info[_GLOBAL_DIRTY] = True


@event.listens_for(Session, "after_commit")
def _bump(session: Session) -> None:
    tenants = session.info.pop(_TENANT_DIRTY, set())
    clock = session.info.pop(_GLOBAL_DIRTY, False)
    kv = get_kv()
    for t in tenants:
        kv.incr(f"ver:{t}")
    if clock:
        kv.incr("ver:global")


@event.listens_for(Session, "after_rollback")
def _discard(session: Session) -> None:
    session.info.pop(_TENANT_DIRTY, None)
    session.info.pop(_GLOBAL_DIRTY, None)


def invalidate_all() -> None:
    get_kv().incr("ver:global")


def cached(name: str, tenant: str, build: Callable[[], Any]) -> tuple[Any, bool]:
    """Return (value, hit). The value must be JSON-serialisable."""
    s = get_settings()
    if not s.cache_enabled:
        return build(), False
    kv = get_kv()
    key = f"cache:{name}:{tenant}:{kv.get(f'ver:{tenant}') or 0}:{kv.get('ver:global') or 0}"
    hit = kv.get(key)
    if hit is not None:
        return json.loads(hit), True
    value = build()
    kv.set(key, json.dumps(value, default=str), s.cache_ttl_seconds)
    return value, False
