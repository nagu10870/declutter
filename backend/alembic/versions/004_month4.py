"""Month 4 — CLIP embeddings, share links, email preferences

Revision ID: 004_month4
Revises: 003_month3
"""
from alembic import op
import sqlalchemy as sa

revision = '004_month4'
down_revision = '003_month3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable pgvector extension ────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── clip_embeddings ──────────────────────────────────────────────────
    op.create_table(
        'clip_embeddings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('file_id', sa.String(36),
                  sa.ForeignKey('file_records.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('embedding_json', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_clip_embeddings_file_id', 'clip_embeddings', ['file_id'])

    # Add pgvector column for actual cosine similarity (if pgvector available)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE clip_embeddings ADD COLUMN IF NOT EXISTS embedding vector(512);
        EXCEPTION WHEN undefined_object THEN
            RAISE NOTICE 'pgvector not available, skipping vector column';
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_clip_embeddings_vector
        ON clip_embeddings USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """.replace("DO $", "DO $"))

    # ── share_links ──────────────────────────────────────────────────────
    op.create_table(
        'share_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('slug', sa.String(20), nullable=False, unique=True),
        sa.Column('link_type', sa.String(30), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('token', sa.Text, nullable=False),
        sa.Column('revoked', sa.Boolean, server_default='FALSE', nullable=False),
        sa.Column('views', sa.Integer, server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_share_links_user_id', 'share_links', ['user_id'])
    op.create_index('ix_share_links_slug', 'share_links', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_table('share_links')
    op.drop_table('clip_embeddings')
