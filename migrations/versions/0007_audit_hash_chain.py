"""audit hash chain

Revision ID: 0007
Revises: 0006

Per-tenant SHA-256 hash chain on audit_log (api/audit_chain.py). Existing rows are chained in id order.
On PostgreSQL a trigger makes chained rows immutable: no UPDATE, no DELETE (TRUNCATE by the owner still works,
which is how the demo reset empties the table).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

TRIGGER_FN = """
CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'audit_log is append-only';
  END IF;
  -- The only update allowed is the one that places a fresh row in the chain.
  IF OLD.chain_seq IS NOT NULL
     OR (NEW.tenant_id, NEW.ts, NEW."user", NEW.role, NEW.agent, NEW.tool, NEW.action, NEW.application_id,
         NEW.inputs::text, NEW.output_hash)
        IS DISTINCT FROM
        (OLD.tenant_id, OLD.ts, OLD."user", OLD.role, OLD.agent, OLD.tool, OLD.action, OLD.application_id,
         OLD.inputs::text, OLD.output_hash) THEN
    RAISE EXCEPTION 'audit_log rows cannot be changed once written';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.add_column('audit_log', sa.Column('chain_seq', sa.Integer(), nullable=True))
    op.add_column('audit_log', sa.Column('prev_hash', sa.String(length=64), nullable=True))
    op.add_column('audit_log', sa.Column('row_hash', sa.String(length=64), nullable=True))
    op.create_index('ux_audit_log_tenant_chain_seq', 'audit_log', ['tenant_id', 'chain_seq'], unique=True)

    from api.audit_chain import GENESIS, row_hash

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("SELECT set_config('app.tenant_bypass', 'on', true)"))
    rows = conn.execute(sa.text(
        'SELECT id, tenant_id, ts, "user", role, agent, tool, action, application_id, inputs, output_hash '
        "FROM audit_log ORDER BY tenant_id, id")).mappings().all()
    heads: dict[str, tuple[int, str]] = {}
    for r in rows:
        seq, prev = heads.get(r["tenant_id"], (0, GENESIS))
        data = dict(r)
        if isinstance(data["inputs"], str):
            import json

            data["inputs"] = json.loads(data["inputs"])
        digest = row_hash(data, seq + 1, prev)
        conn.execute(sa.text("UPDATE audit_log SET chain_seq = :s, prev_hash = :p, row_hash = :h WHERE id = :i"),
                     {"s": seq + 1, "p": prev, "h": digest, "i": r["id"]})
        heads[r["tenant_id"]] = (seq + 1, digest)

    if conn.dialect.name == "postgresql":
        op.execute(TRIGGER_FN)
        op.execute("CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log "
                   "FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    op.drop_index('ux_audit_log_tenant_chain_seq', table_name='audit_log')
    op.drop_column('audit_log', 'row_hash')
    op.drop_column('audit_log', 'prev_hash')
    op.drop_column('audit_log', 'chain_seq')
