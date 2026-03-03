"""Month 2 — cloud connections, pHash index, thumbnail_url column

Revision ID: 002_month2
Revises: 001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '002_month2'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add perceptual_hash index for fast similarity queries
    op.create_index(
        'ix_file_records_phash',
        'file_records',
        ['perceptual_hash'],
        postgresql_where=sa.text("perceptual_hash IS NOT NULL"),
    )

    # Add mime_type index for filtering image/* files efficiently
    op.create_index(
        'ix_file_records_mime',
        'file_records',
        ['mime_type'],
        postgresql_where=sa.text("mime_type IS NOT NULL"),
    )

    # Composite index for per-user image queries (pHash similarity scan)
    op.create_index(
        'ix_file_records_user_mime_phash',
        'file_records',
        ['user_id', 'mime_type', 'perceptual_hash'],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )

    # oauth_state table — CSRF protection for OAuth flows
    op.create_table(
        'oauth_states',
        sa.Column('state', sa.String(128), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Add sync_status column to storage_connections
    op.add_column(
        'storage_connections',
        sa.Column('sync_status', sa.String(20), server_default='idle', nullable=False),
    )
    op.add_column(
        'storage_connections',
        sa.Column('sync_error', sa.Text(), nullable=True),
    )
    op.add_column(
        'storage_connections',
        sa.Column('files_indexed', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('storage_connections', 'files_indexed')
    op.drop_column('storage_connections', 'sync_error')
    op.drop_column('storage_connections', 'sync_status')
    op.drop_table('oauth_states')
    op.drop_index('ix_file_records_user_mime_phash', 'file_records')
    op.drop_index('ix_file_records_mime', 'file_records')
    op.drop_index('ix_file_records_phash', 'file_records')
