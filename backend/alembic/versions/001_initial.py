"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('tier', sa.String(20), server_default='free', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Storage connections
    op.create_table(
        'storage_connections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('oauth_token_enc', sa.Text()),
        sa.Column('refresh_token_enc', sa.Text()),
        sa.Column('account_email', sa.String(255)),
        sa.Column('total_bytes', sa.BigInteger()),
        sa.Column('used_bytes', sa.BigInteger()),
        sa.Column('last_synced', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_storage_connections_user_id', 'storage_connections', ['user_id'])

    # Scan jobs
    op.create_table(
        'scan_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('connection_id', sa.String(36), sa.ForeignKey('storage_connections.id', ondelete='CASCADE')),
        sa.Column('status', sa.String(20), server_default='queued'),
        sa.Column('scan_type', sa.String(30), server_default='full'),
        sa.Column('files_scanned', sa.Integer(), server_default='0'),
        sa.Column('files_total', sa.Integer()),
        sa.Column('bytes_reclaimable', sa.BigInteger(), server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_scan_jobs_user_id', 'scan_jobs', ['user_id'])

    # File records
    op.create_table(
        'file_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('connection_id', sa.String(36), sa.ForeignKey('storage_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('remote_id', sa.String(512)),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_name', sa.String(512), nullable=False),
        sa.Column('file_size', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('mime_type', sa.String(128)),
        sa.Column('md5_hash', sa.String(32)),
        sa.Column('sha256_hash', sa.String(64)),
        sa.Column('perceptual_hash', sa.String(64)),
        sa.Column('last_modified', sa.DateTime(timezone=True)),
        sa.Column('created_date', sa.DateTime(timezone=True)),
        sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('thumbnail_key', sa.String(512)),
    )
    op.create_index('ix_file_records_user_id', 'file_records', ['user_id'])
    op.create_index('ix_file_records_md5', 'file_records', ['md5_hash'])
    op.create_index('ix_file_records_size', 'file_records', ['file_size'])

    # Duplicate groups
    op.create_table(
        'duplicate_groups',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('match_type', sa.String(20), nullable=False),
        sa.Column('similarity', sa.Float(), server_default='1.0'),
        sa.Column('total_wasted_bytes', sa.BigInteger(), server_default='0'),
        sa.Column('resolved', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_duplicate_groups_user_id', 'duplicate_groups', ['user_id'])

    # Cleanup actions
    op.create_table(
        'cleanup_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', sa.String(36), sa.ForeignKey('file_records.id')),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('action_by', sa.String(20), server_default='user'),
        sa.Column('bytes_freed', sa.BigInteger(), server_default='0'),
        sa.Column('undo_data', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('undone_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_cleanup_actions_user_id', 'cleanup_actions', ['user_id'])


def downgrade() -> None:
    op.drop_table('cleanup_actions')
    op.drop_table('duplicate_groups')
    op.drop_table('file_records')
    op.drop_table('scan_jobs')
    op.drop_table('storage_connections')
    op.drop_table('users')
