"""refresh tokens

Revision ID: 0005
Revises: 0004

Rotating refresh tokens (hash only), tenant-scoped with row-level security.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

POLICY = ("tenant_id = current_setting('app.tenant_id', true) "
          "OR current_setting('app.tenant_bypass', true) = 'on'")


def upgrade() -> None:
    op.create_table('refresh_tokens',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('family_id', sa.String(length=32), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('replaced_by', sa.String(length=32), nullable=True),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_family_id'), 'refresh_tokens', ['family_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_tenant_id'), 'refresh_tokens', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_username'), 'refresh_tokens', ['username'], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON refresh_tokens USING ({POLICY}) WITH CHECK ({POLICY})")


def downgrade() -> None:
    op.drop_index(op.f('ix_refresh_tokens_username'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_tenant_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_family_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
