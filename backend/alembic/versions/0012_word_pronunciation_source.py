"""add per-word pronunciation source

Revision ID: 0012_word_pronunciation_source
Revises: 0011_default_pronunciation_voice
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = '0012_word_pronunciation_source'
down_revision = '0011_default_pronunciation_voice'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('word_items') and 'pronunciation_source' not in {column['name'] for column in inspector.get_columns('word_items')}:
        op.add_column('word_items', sa.Column('pronunciation_source', sa.String(length=20), nullable=False, server_default='default'))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('word_items') and 'pronunciation_source' in {column['name'] for column in inspector.get_columns('word_items')}:
        op.drop_column('word_items', 'pronunciation_source')
