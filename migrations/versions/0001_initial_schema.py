"""initial schema

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table('ai_usage',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('agent', sa.String(length=48), nullable=False),
    sa.Column('template_id', sa.String(length=64), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('latency_ms', sa.Float(), nullable=False),
    sa.Column('tokens_est', sa.Integer(), nullable=False),
    sa.Column('fallback', sa.Boolean(), nullable=False),
    sa.Column('user', sa.String(length=64), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_usage_application_id'), 'ai_usage', ['application_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_tenant_id'), 'ai_usage', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_ts'), 'ai_usage', ['ts'], unique=False)
    op.create_table('applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('state', sa.String(length=24), nullable=False),
    sa.Column('channel', sa.String(length=16), nullable=False),
    sa.Column('requested_amount', sa.Float(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('band', sa.String(length=16), nullable=True),
    sa.Column('pd_12m', sa.Float(), nullable=True),
    sa.Column('score_month', sa.Integer(), nullable=True),
    sa.Column('score_detail', sa.JSON(), nullable=True),
    sa.Column('data_checks', sa.JSON(), nullable=True),
    sa.Column('memo', sa.JSON(), nullable=True),
    sa.Column('memo_pdf', sa.String(length=256), nullable=True),
    sa.Column('recommended_limit', sa.Float(), nullable=True),
    sa.Column('pricing_band', sa.String(length=64), nullable=True),
    sa.Column('decision', sa.String(length=16), nullable=True),
    sa.Column('decision_comment', sa.Text(), nullable=True),
    sa.Column('decided_by', sa.String(length=64), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('kfs', sa.JSON(), nullable=True),
    sa.Column('sanctioned_limit', sa.Float(), nullable=True),
    sa.Column('disbursement_ref', sa.String(length=64), nullable=True),
    sa.Column('disbursed_on', sa.Date(), nullable=True),
    sa.Column('last_ews_month', sa.Integer(), nullable=True),
    sa.Column('review_requested', sa.Boolean(), nullable=False),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('plan_cache', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_applications_factory_id'), 'applications', ['factory_id'], unique=False)
    op.create_index('ix_applications_tenant_factory', 'applications', ['tenant_id', 'factory_id'], unique=False)
    op.create_index(op.f('ix_applications_tenant_id'), 'applications', ['tenant_id'], unique=False)
    op.create_index('ix_applications_tenant_state', 'applications', ['tenant_id', 'state'], unique=False)
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('agent', sa.String(length=48), nullable=False),
    sa.Column('tool', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('inputs', sa.JSON(), nullable=True),
    sa.Column('output_hash', sa.String(length=64), nullable=True),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_application_id'), 'audit_log', ['application_id'], unique=False)
    op.create_index(op.f('ix_audit_log_tenant_id'), 'audit_log', ['tenant_id'], unique=False)
    op.create_index('ix_audit_log_tenant_id_id', 'audit_log', ['tenant_id', 'id'], unique=False)
    op.create_index(op.f('ix_audit_log_ts'), 'audit_log', ['ts'], unique=False)
    op.create_table('consent_ledger',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('consent_id', sa.String(length=40), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('event', sa.String(length=32), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('actor', sa.String(length=64), nullable=False),
    sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consent_ledger_consent_id'), 'consent_ledger', ['consent_id'], unique=False)
    op.create_index(op.f('ix_consent_ledger_factory_id'), 'consent_ledger', ['factory_id'], unique=False)
    op.create_index(op.f('ix_consent_ledger_tenant_id'), 'consent_ledger', ['tenant_id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('channel', sa.String(length=16), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('text_hi', sa.Text(), nullable=True),
    sa.Column('sim_date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_factory_id'), 'notifications', ['factory_id'], unique=False)
    op.create_index(op.f('ix_notifications_tenant_id'), 'notifications', ['tenant_id'], unique=False)
    op.create_table('plan_progress',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('step_key', sa.String(length=64), nullable=False),
    sa.Column('done_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plan_progress_factory_id'), 'plan_progress', ['factory_id'], unique=False)
    op.create_index(op.f('ix_plan_progress_tenant_id'), 'plan_progress', ['tenant_id'], unique=False)
    op.create_table('sim_clock',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('current_date', sa.Date(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tenants',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('display_name', sa.String(length=128), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=True),
    sa.Column('branch', sa.String(length=32), nullable=True),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    op.create_table('alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('severity', sa.String(length=8), nullable=False),
    sa.Column('rules', sa.JSON(), nullable=False),
    sa.Column('reasons', sa.JSON(), nullable=False),
    sa.Column('next_best_action', sa.String(length=64), nullable=False),
    sa.Column('briefing', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('action_taken', sa.String(length=64), nullable=True),
    sa.Column('action_note', sa.Text(), nullable=True),
    sa.Column('actioned_by', sa.String(length=64), nullable=True),
    sa.Column('outcome', sa.String(length=32), nullable=True),
    sa.Column('owner', sa.String(length=64), nullable=True),
    sa.Column('acknowledged_by', sa.String(length=64), nullable=True),
    sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('raised_on', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_application_id'), 'alerts', ['application_id'], unique=False)
    op.create_index(op.f('ix_alerts_factory_id'), 'alerts', ['factory_id'], unique=False)
    op.create_index(op.f('ix_alerts_tenant_id'), 'alerts', ['tenant_id'], unique=False)
    op.create_index('ix_alerts_tenant_status_severity', 'alerts', ['tenant_id', 'status', 'severity'], unique=False)
    op.create_table('consents',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('purpose', sa.String(length=256), nullable=False),
    sa.Column('fi_types', sa.JSON(), nullable=False),
    sa.Column('data_from', sa.Date(), nullable=False),
    sa.Column('data_to', sa.Date(), nullable=False),
    sa.Column('expires_on', sa.Date(), nullable=False),
    sa.Column('frequency', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consents_application_id'), 'consents', ['application_id'], unique=False)
    op.create_index(op.f('ix_consents_factory_id'), 'consents', ['factory_id'], unique=False)
    op.create_index(op.f('ix_consents_tenant_id'), 'consents', ['tenant_id'], unique=False)
    op.create_table('data_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('factory_id', sa.String(length=16), nullable=False),
    sa.Column('upto_month', sa.Integer(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('pulled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_data_snapshots_application_id'), 'data_snapshots', ['application_id'], unique=False)
    op.create_index(op.f('ix_data_snapshots_factory_id'), 'data_snapshots', ['factory_id'], unique=False)
    op.create_index(op.f('ix_data_snapshots_tenant_id'), 'data_snapshots', ['tenant_id'], unique=False)



def downgrade() -> None:

    op.drop_index(op.f('ix_data_snapshots_tenant_id'), table_name='data_snapshots')
    op.drop_index(op.f('ix_data_snapshots_factory_id'), table_name='data_snapshots')
    op.drop_index(op.f('ix_data_snapshots_application_id'), table_name='data_snapshots')
    op.drop_table('data_snapshots')
    op.drop_index(op.f('ix_consents_tenant_id'), table_name='consents')
    op.drop_index(op.f('ix_consents_factory_id'), table_name='consents')
    op.drop_index(op.f('ix_consents_application_id'), table_name='consents')
    op.drop_table('consents')
    op.drop_index('ix_alerts_tenant_status_severity', table_name='alerts')
    op.drop_index(op.f('ix_alerts_tenant_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_factory_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_application_id'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_table('users')
    op.drop_table('tenants')
    op.drop_table('sim_clock')
    op.drop_index(op.f('ix_plan_progress_tenant_id'), table_name='plan_progress')
    op.drop_index(op.f('ix_plan_progress_factory_id'), table_name='plan_progress')
    op.drop_table('plan_progress')
    op.drop_index(op.f('ix_notifications_tenant_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_factory_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_consent_ledger_tenant_id'), table_name='consent_ledger')
    op.drop_index(op.f('ix_consent_ledger_factory_id'), table_name='consent_ledger')
    op.drop_index(op.f('ix_consent_ledger_consent_id'), table_name='consent_ledger')
    op.drop_table('consent_ledger')
    op.drop_index(op.f('ix_audit_log_ts'), table_name='audit_log')
    op.drop_index('ix_audit_log_tenant_id_id', table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_tenant_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_application_id'), table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index('ix_applications_tenant_state', table_name='applications')
    op.drop_index(op.f('ix_applications_tenant_id'), table_name='applications')
    op.drop_index('ix_applications_tenant_factory', table_name='applications')
    op.drop_index(op.f('ix_applications_factory_id'), table_name='applications')
    op.drop_table('applications')
    op.drop_index(op.f('ix_ai_usage_ts'), table_name='ai_usage')
    op.drop_index(op.f('ix_ai_usage_tenant_id'), table_name='ai_usage')
    op.drop_index(op.f('ix_ai_usage_application_id'), table_name='ai_usage')
    op.drop_table('ai_usage')

