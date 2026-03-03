"""Month 5-6 — API keys, webhooks, audit logs, account preferences

Revision ID: 005_month5_6
Revises: 004_month4
"""
from alembic import op
import sqlalchemy as sa

revision = '005_month5_6'
down_revision = '004_month4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── api_keys ─────────────────────────────────────────────────────────
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('scopes', sa.String(255), server_default="'read'", nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_ip', sa.String(45), nullable=True),
        sa.Column('revoked', sa.Boolean, server_default='FALSE', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)

    # ── audit_logs ────────────────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])

    # ── webhook_endpoints ─────────────────────────────────────────────────
    op.create_table(
        'webhook_endpoints',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('secret', sa.String(64), nullable=False),
        sa.Column('events', sa.JSON, nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='TRUE', nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_count', sa.Integer, server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_webhook_endpoints_user_id', 'webhook_endpoints', ['user_id'])

    # ── users: preferences column (Month 6) ──────────────────────────────
    op.add_column('users', sa.Column('preferences', sa.JSON, nullable=True))

    # ── file_records: is_favorite + notes (Month 6) ───────────────────────
    op.add_column('file_records', sa.Column('is_favorite', sa.Boolean,
                  server_default='FALSE', nullable=False))
    op.add_column('file_records', sa.Column('notes', sa.Text, nullable=True))

    # ── storage_connections: nickname (Month 6) ───────────────────────────
    op.add_column('storage_connections', sa.Column('nickname', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('storage_connections', 'nickname')
    op.drop_column('file_records', 'notes')
    op.drop_column('file_records', 'is_favorite')
    op.drop_column('users', 'preferences')
    op.drop_table('webhook_endpoints')
    op.drop_table('audit_logs')
    op.drop_table('api_keys')
