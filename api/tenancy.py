"""Multi-tenancy: one bank is one tenant. Enforced at the session (repository) layer, so no query in
a router or an agent can forget the filter.

- Every business table carries `tenant_id` (`TenantScoped`).
- A session bound to a tenant (`session.info["tenant_id"]`) gets `WHERE tenant_id = :tid` added to every
  ORM select, update and delete on those tables, including `Session.get` and relationship loads.
- New rows are stamped with the session's tenant; a row for another tenant is rejected.
- Request sessions are fail-closed: touching a tenant table before the tenant is known raises.
- On PostgreSQL the same value is set as `app.tenant_id` for Row-Level Security (defence in depth).
"""

from __future__ import annotations

from sqlalchemy import String, event, text
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column, with_loader_criteria

TENANT_KEY, ENFORCE_KEY, BYPASS_KEY = "tenant_id", "tenant_enforce", "tenant_bypass"


class TenantScoped:
    """Mixin for tables that belong to one bank."""

    tenant_id: Mapped[str] = mapped_column(String(32), index=True)


class TenantIsolationError(RuntimeError):
    pass


def bind_tenant(session: Session, tenant_id: str) -> None:
    session.info[TENANT_KEY] = tenant_id
    session.info.pop(BYPASS_KEY, None)
    _apply_rls(session)


def allow_cross_tenant(session: Session) -> None:
    """Explicit opt-out for the few places that must look across tenants (login lookup, seeding)."""
    session.info[BYPASS_KEY] = True


def _apply_rls(session: Session) -> None:
    if session.get_bind().dialect.name == "postgresql" and session.in_transaction():
        session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": session.info.get(TENANT_KEY, "")})


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete):
        return
    session = state.session
    if session.info.get(BYPASS_KEY):
        return
    tenant = session.info.get(TENANT_KEY)
    if tenant is None:
        if session.info.get(ENFORCE_KEY) and _touches_tenant_table(state):
            raise TenantIsolationError("Tenant-scoped data was queried before the tenant was known")
        return
    state.statement = state.statement.options(
        with_loader_criteria(TenantScoped, lambda cls: cls.tenant_id == tenant, include_aliases=True)
    )


def _touches_tenant_table(state: ORMExecuteState) -> bool:
    return any(isinstance(m.class_, type) and issubclass(m.class_, TenantScoped) for m in state.all_mappers)


@event.listens_for(Session, "before_flush")
def _stamp_tenant(session: Session, _ctx, _instances) -> None:
    tenant = session.info.get(TENANT_KEY)
    for obj in session.new:
        if not isinstance(obj, TenantScoped):
            continue
        if obj.tenant_id is None:
            if tenant is None:
                raise TenantIsolationError(f"{type(obj).__name__} created without a tenant")
            obj.tenant_id = tenant
        elif tenant is not None and obj.tenant_id != tenant and not session.info.get(BYPASS_KEY):
            raise TenantIsolationError(f"{type(obj).__name__} belongs to another tenant")


@event.listens_for(Session, "after_begin")
def _rls_on_begin(session: Session, _transaction, connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": session.info.get(TENANT_KEY, "")})
