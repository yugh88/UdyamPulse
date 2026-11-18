"""Partitioned serving table and row-level security.

Revision ID: 0002
Revises: 0001

`account_scores` is RANGE-partitioned by month on PostgreSQL. Row-Level Security is defence in depth
behind the application-level tenant filter (`api/tenancy.py`): even a query that forgot its WHERE
clause returns only the current tenant's rows.
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TENANT_TABLES = ("users", "applications", "consents", "consent_ledger", "data_snapshots", "alerts", "notifications",
                 "audit_log", "ai_usage", "plan_progress", "account_scores")
# Monthly partitions created up front; later months are added by `api.serving.ensure_partition`.
FIRST_MONTH, LAST_MONTH = date(2024, 1, 1), date(2027, 12, 1)

POLICY = ("tenant_id = current_setting('app.tenant_id', true) "
          "OR current_setting('app.tenant_bypass', true) = 'on'")


def _months(first: date, last: date):
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        nxt = (y + (m == 12), m % 12 + 1)
        yield date(y, m, 1), date(nxt[0], nxt[1], 1)
        y, m = nxt


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        op.create_table(
            "account_scores",
            sa.Column("tenant_id", sa.String(32), primary_key=True),
            sa.Column("factory_id", sa.String(16), primary_key=True),
            sa.Column("month_date", sa.Date, primary_key=True),
            sa.Column("month", sa.Integer, nullable=False),
            sa.Column("application_id", sa.Integer, nullable=False),
            sa.Column("score", sa.Integer, nullable=False),
            sa.Column("band", sa.String(16), nullable=False),
            sa.Column("pd_12m", sa.Float, nullable=False),
        )
        op.create_index("ix_account_scores_tenant_month", "account_scores", ["tenant_id", "month"])
        return

    op.execute("""
        CREATE TABLE account_scores (
            tenant_id      varchar(32) NOT NULL,
            factory_id     varchar(16) NOT NULL,
            month_date     date        NOT NULL,
            month          integer     NOT NULL,
            application_id integer     NOT NULL,
            score          integer     NOT NULL,
            band           varchar(16) NOT NULL,
            pd_12m         double precision NOT NULL,
            PRIMARY KEY (tenant_id, factory_id, month_date)
        ) PARTITION BY RANGE (month_date)
    """)
    for start, end in _months(FIRST_MONTH, LAST_MONTH):
        op.execute(f"CREATE TABLE account_scores_{start:%Y_%m} PARTITION OF account_scores "
                   f"FOR VALUES FROM ('{start}') TO ('{end}')")
    op.execute("CREATE TABLE account_scores_default PARTITION OF account_scores DEFAULT")
    op.execute("CREATE INDEX ix_account_scores_tenant_month ON account_scores (tenant_id, month)")

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")  # applies to the table owner too
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("account_scores")
