"""branch scope

Revision ID: 0008
Revises: 0007

Applications record their factory's cluster; staff carry the clusters they cover (api/authz.py).
Existing applications keep a NULL cluster, which only bank-wide roles can see, until re-seeded or backfilled.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('applications', sa.Column('cluster', sa.String(length=32), nullable=True))
    op.create_index('ix_applications_tenant_cluster', 'applications', ['tenant_id', 'cluster'], unique=False)
    with op.batch_alter_table('users') as batch:
        batch.alter_column('branch', existing_type=sa.String(length=32), type_=sa.String(length=128),
                           existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.alter_column('branch', existing_type=sa.String(length=128), type_=sa.String(length=32),
                           existing_nullable=True)
    op.drop_index('ix_applications_tenant_cluster', table_name='applications')
    op.drop_column('applications', 'cluster')
