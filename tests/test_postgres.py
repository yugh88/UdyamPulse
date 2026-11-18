"""PostgreSQL-only guarantees: migrations match the models, the serving table is partitioned by month,
and Row-Level Security isolates tenants even for raw SQL that has no WHERE clause.

Run with: UP_TEST_DB_URL=postgresql+psycopg://udyam_app@127.0.0.1:55432/udyampulse_test pytest"""

import pytest
from sqlalchemy import text

from api.models.db import get_engine, is_postgres

pytestmark = pytest.mark.skipif(not is_postgres(), reason="needs PostgreSQL (set UP_TEST_DB_URL)")
TABLES = ("applications", "alerts", "audit_log", "account_scores", "users")


def _count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def _as(conn, tenant: str, bypass: str = "off") -> None:
    conn.execute(text("SELECT set_config('app.tenant_id', :t, true), set_config('app.tenant_bypass', :b, true)"),
                 {"t": tenant, "b": bypass})


def test_app_role_cannot_bypass_rls(client):
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert tuple(row) == (False, False), "tests must run as a role that is subject to row-level security"


def test_rls_filters_raw_sql_without_a_where_clause(client):
    engine = get_engine()
    with engine.begin() as conn:
        _as(conn, "", "on")
        total = {t: _count(conn, t) for t in TABLES}
    with engine.begin() as conn:
        _as(conn, "bank-a")
        a = {t: _count(conn, t) for t in TABLES}
        assert conn.execute(text("SELECT DISTINCT tenant_id FROM applications")).scalars().all() == ["bank-a"]
    with engine.begin() as conn:
        _as(conn, "bank-b")
        b = {t: _count(conn, t) for t in TABLES}
    for t in TABLES:
        assert 0 < b[t] < a[t] < total[t] and a[t] + b[t] == total[t], t
    with engine.begin() as conn:  # no tenant and no bypass: nothing is visible (fail closed)
        _as(conn, "")
        assert all(_count(conn, t) == 0 for t in TABLES)


def test_rls_blocks_cross_tenant_writes(client):
    from sqlalchemy.exc import DBAPIError

    engine = get_engine()
    with engine.begin() as conn:
        _as(conn, "bank-b")
        assert conn.execute(text("UPDATE alerts SET owner = 'rm2' WHERE tenant_id = 'bank-a'")).rowcount == 0
        assert conn.execute(text("DELETE FROM applications WHERE tenant_id = 'bank-a'")).rowcount == 0
    with pytest.raises(DBAPIError, match="row-level security"), engine.begin() as conn:
        _as(conn, "bank-b")
        conn.execute(text("INSERT INTO plan_progress (tenant_id, factory_id, step_key, done_at) "
                          "VALUES ('bank-a', 'UP-F0001', 'forged', now())"))


def test_account_scores_is_partitioned_by_month_and_prunes(client):
    with get_engine().begin() as conn:
        _as(conn, "", "on")
        strategy = conn.execute(text("SELECT partstrat FROM pg_partitioned_table "
                                     "WHERE partrelid = 'account_scores'::regclass")).scalar()
        assert strategy == "r"
        parts = conn.execute(text("SELECT inhrelid::regclass::text FROM pg_inherits "
                                  "WHERE inhparent = 'account_scores'::regclass")).scalars().all()
        assert "account_scores_2026_06" in parts and "account_scores_default" in parts and len(parts) >= 40
        assert _count(conn, "account_scores_default") == 0, "every seeded month has its own partition"
        assert _count(conn, "account_scores_2026_05") > 0
        plan = "\n".join(conn.execute(text("EXPLAIN SELECT * FROM account_scores "
                                           "WHERE month_date = DATE '2026-05-01'")).scalars())
        assert "account_scores_2026_05" in plan and "account_scores_2026_04" not in plan


def test_migrations_match_the_models(client):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from api.models.db import Base

    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    def is_partition_object(change) -> bool:
        # Monthly partitions and their indexes are created by raw SQL in migration 0002, not by the ORM.
        obj = change[1]
        table = getattr(obj, "table", obj)
        return change[0] in ("remove_table", "remove_index") and table.name.startswith("account_scores_")

    drift = [f"{c[0]}: {getattr(c[1], 'name', c[1])}" for c in diff if not is_partition_object(c)]
    assert drift == [], "models and migrations have drifted"


def test_ensure_partition_creates_a_future_month(client):
    from datetime import date

    from api.models.db import SessionLocal
    from api.serving import ensure_partition

    with SessionLocal() as db:
        ensure_partition(db, date(2030, 1, 1))
        ensure_partition(db, date(2030, 1, 1))  # idempotent
        assert db.execute(text("SELECT to_regclass('account_scores_2030_01')")).scalar() is not None
        db.rollback()
