"""jobs and outbox

Revision ID: 0003
Revises: 0002

Background jobs and the transactional outbox, both tenant-scoped with row-level security.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

POLICY = ("tenant_id = current_setting('app.tenant_id', true) "
          "OR current_setting('app.tenant_bypass', true) = 'on'")


def upgrade() -> None:
    op.create_table('jobs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('message', sa.String(length=256), nullable=True),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_tenant_id'), 'jobs', ['tenant_id'], unique=False)
    op.create_index('ix_jobs_tenant_updated', 'jobs', ['tenant_id', 'updated_at'], unique=False)
    op.create_table('outbox',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outbox_tenant_id'), 'outbox', ['tenant_id'], unique=False)
    op.create_index('ix_outbox_unpublished', 'outbox', ['published_at', 'id'], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("jobs", "outbox"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    op.drop_index('ix_outbox_unpublished', table_name='outbox')
    op.drop_index(op.f('ix_outbox_tenant_id'), table_name='outbox')
    op.drop_table('outbox')
    op.drop_index('ix_jobs_tenant_updated', table_name='jobs')
    op.drop_index(op.f('ix_jobs_tenant_id'), table_name='jobs')
    op.drop_table('jobs')
