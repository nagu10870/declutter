"""Month 3 — AI classification, suggestions engine, schedules

Revision ID: 003_month3
Revises: 002_month2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_month3'
down_revision = '002_month2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── file_classifications ──────────────────────────────────────────────
    op.create_table(
        'file_classifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('file_id', sa.String(36),
                  sa.ForeignKey('file_records.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('sub_category', sa.String(50), nullable=True),
        sa.Column('tags', sa.JSON, nullable=True),
        sa.Column('is_blurry', sa.Boolean, server_default='FALSE', nullable=False),
        sa.Column('blur_score', sa.Float, nullable=True),
        sa.Column('is_screenshot', sa.Boolean, server_default='FALSE', nullable=False),
        sa.Column('confidence', sa.Float, server_default='0', nullable=False),
        sa.Column('model_version', sa.String(50), server_default="'heuristic'", nullable=False),
        sa.Column('classified_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_file_classifications_file_id', 'file_classifications', ['file_id'])
    op.create_index('ix_file_classifications_user_id', 'file_classifications', ['user_id'])
    op.create_index('ix_file_classifications_category', 'file_classifications', ['category'],
                    postgresql_where=sa.text("category IS NOT NULL"))
    op.create_index('ix_file_classifications_blurry', 'file_classifications', ['is_blurry'],
                    postgresql_where=sa.text("is_blurry = TRUE"))
    op.create_index('ix_file_classifications_screenshot', 'file_classifications', ['is_screenshot'],
                    postgresql_where=sa.text("is_screenshot = TRUE"))

    # ── suggestions ───────────────────────────────────────────────────────
    op.create_table(
        'suggestions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('suggestion_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('file_ids', sa.JSON, nullable=False),
        sa.Column('bytes_savings', sa.BigInteger, server_default='0', nullable=False),
        sa.Column('risk_level', sa.String(10), server_default="'low'", nullable=False),
        sa.Column('action', sa.String(20), server_default="'delete'", nullable=False),
        sa.Column('action_label', sa.String(50), server_default="'Delete All'", nullable=False),
        sa.Column('dismissed', sa.Boolean, server_default='FALSE', nullable=False),
        sa.Column('applied', sa.Boolean, server_default='FALSE', nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_suggestions_user_id', 'suggestions', ['user_id'])
    op.create_index(
        'ix_suggestions_active',
        'suggestions',
        ['user_id', 'dismissed', 'applied'],
        postgresql_where=sa.text("dismissed = FALSE AND applied = FALSE"),
    )

    # ── schedules ─────────────────────────────────────────────────────────
    op.create_table(
        'schedules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='TRUE', nullable=False),
        sa.Column('cron_expr', sa.String(50), nullable=False),
        sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_schedules_user_id', 'schedules', ['user_id'])

    # ── stripe_customer_id on users ───────────────────────────────────────
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(64), nullable=True))
    op.create_index('ix_users_stripe_customer', 'users', ['stripe_customer_id'],
                    postgresql_where=sa.text("stripe_customer_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index('ix_users_stripe_customer', 'users')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_table('schedules')
    op.drop_table('suggestions')
    op.drop_table('file_classifications')
