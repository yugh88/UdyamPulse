"""batch runs and checkpoints

Revision ID: 0004
Revises: 0003

Checkpoint tables for the chunked nightly batch. Platform-level operational data, so no tenant column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('batch_runs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('shards', sa.Integer(), nullable=False),
    sa.Column('chunk_size', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('total_accounts', sa.Integer(), nullable=False),
    sa.Column('total_chunks', sa.Integer(), nullable=False),
    sa.Column('stats', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('batch_chunks',
    sa.Column('run_id', sa.String(length=32), nullable=False),
    sa.Column('chunk_no', sa.Integer(), nullable=False),
    sa.Column('shard', sa.Integer(), nullable=False),
    sa.Column('accounts', sa.Integer(), nullable=False),
    sa.Column('alerts', sa.Integer(), nullable=False),
    sa.Column('seconds', sa.Float(), nullable=False),
    sa.Column('worker', sa.String(length=64), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['batch_runs.id'], ),
    sa.PrimaryKeyConstraint('run_id', 'chunk_no')
    )


def downgrade() -> None:
    op.drop_table('batch_chunks')
    op.drop_table('batch_runs')
