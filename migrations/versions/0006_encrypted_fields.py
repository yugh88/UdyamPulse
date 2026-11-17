"""encrypted fields

Revision ID: 0006
Revises: 0005

Columns holding personal data or free text become TEXT so they can hold Fernet ciphertext (api/crypto.py).
Existing plaintext stays readable; `python -m api.crypto rotate` encrypts it in place.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.alter_column('display_name', existing_type=sa.String(length=128), type_=sa.Text(), existing_nullable=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE data_snapshots ALTER COLUMN payload TYPE TEXT USING payload::text")
    else:
        with op.batch_alter_table('data_snapshots') as batch:
            batch.alter_column('payload', existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=False)


def downgrade() -> None:
    # Ciphertext cannot be cast back to JSON or VARCHAR(128); restore from a backup taken before 0006 instead.
    raise NotImplementedError("encrypted columns cannot be downgraded in place")
