"""ai usage outcome

Revision ID: 0009
Revises: 0008

Records why each LLM call ended the way it did (cache hit, timeout, breaker open, number guard...).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ai_usage', sa.Column('outcome', sa.String(length=24), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_usage', 'outcome')
