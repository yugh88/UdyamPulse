"""change tracking

Revision ID: 0010
Revises: 0009

What changed, from what, to what, and when (change_events), and when each user last looked at an item
(user_seen). Both tenant-scoped with row-level security. tenants.change_baseline_at marks the end of seeded
history.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

POLICY = ("tenant_id = current_setting('app.tenant_id', true) "
          "OR current_setting('app.tenant_bypass', true) = 'on'")


def upgrade() -> None:
    op.add_column('tenants', sa.Column('change_baseline_at', sa.DateTime(timezone=True), nullable=False,
                                       server_default=sa.func.now()))
    op.create_table('change_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entity_type', sa.String(length=16), nullable=False),
    sa.Column('entity_id', sa.String(length=40), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('event_type', sa.String(length=32), nullable=False),
    sa.Column('before', sa.JSON(), nullable=True),
    sa.Column('after', sa.JSON(), nullable=True),
    sa.Column('summary', sa.String(length=256), nullable=False),
    sa.Column('actor', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_change_events_tenant_id'), 'change_events', ['tenant_id'], unique=False)
    op.create_index('ix_change_events_tenant_app', 'change_events', ['tenant_id', 'application_id', 'id'], unique=False)
    op.create_index('ix_change_events_tenant_entity', 'change_events', ['tenant_id', 'entity_type', 'entity_id', 'id'],
                    unique=False)
    op.create_table('user_seen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=16), nullable=False),
    sa.Column('entity_id', sa.String(length=40), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_seen_tenant_id'), 'user_seen', ['tenant_id'], unique=False)
    op.create_index('ux_user_seen', 'user_seen', ['tenant_id', 'username', 'entity_type', 'entity_id'], unique=True)
    if op.get_bind().dialect.name == "postgresql":
        for table in ("change_events", "user_seen"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    op.drop_index('ux_user_seen', table_name='user_seen')
    op.drop_index(op.f('ix_user_seen_tenant_id'), table_name='user_seen')
    op.drop_table('user_seen')
    op.drop_index('ix_change_events_tenant_entity', table_name='change_events')
    op.drop_index('ix_change_events_tenant_app', table_name='change_events')
    op.drop_index(op.f('ix_change_events_tenant_id'), table_name='change_events')
    op.drop_table('change_events')
    op.drop_column('tenants', 'change_baseline_at')
