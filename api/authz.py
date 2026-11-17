"""Authorisation: role checks (RBAC, `api.auth.require_roles`) plus attribute checks on the account (ABAC).

Policy (docs/THREAT_MODEL.md has the full matrix):

| role            | applications and alerts it can see            | can decide | portfolio views        |
|-----------------|-----------------------------------------------|------------|------------------------|
| risk            | every account of its bank                     | no         | whole bank             |
| credit_officer  | its branch scope (`*` = whole bank, default)  | yes        | its branch scope       |
| rm              | its branch scope only (no branch = nothing)   | no         | its branch scope       |
| msme            | its own factory only                          | no         | none                   |

A user's `branch` lists the factory clusters it covers, comma separated, or `*` for a zonal hub. Bank
isolation sits underneath all of this (api/tenancy.py and PostgreSQL row-level security): branch scope only
ever narrows what a bank's own staff see.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from api.audit import Actor
from api.models.db import Application

ALL = "*"


def branch_clusters(user: Actor) -> frozenset[str] | None:
    """Clusters the user may see, or None for the whole bank."""
    if user.role == "risk":
        return None
    raw = (user.branch or "").strip()
    if user.role == "credit_officer" and not raw:
        return None  # credit officers sit at the hub unless given a branch
    if raw == ALL:
        return None
    return frozenset(c.strip() for c in raw.split(",") if c.strip())  # empty for an RM with no branch: fail closed


def scope_key(user: Actor) -> str:
    clusters = branch_clusters(user)
    return ALL if clusters is None else ",".join(sorted(clusters)) or "-"


def scope_applications(q: Query, user: Actor) -> Query:
    clusters = branch_clusters(user)
    return q if clusters is None else q.filter(Application.cluster.in_(clusters))


def can_see(user: Actor, app: Application) -> bool:
    if user.role == "msme":
        return user.factory_id == app.factory_id
    clusters = branch_clusters(user)
    return clusters is None or app.cluster in clusters


def ensure_branch_access(user: Actor, app: Application) -> None:
    if user.role != "msme" and not can_see(user, app):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account belongs to a branch outside your scope")
