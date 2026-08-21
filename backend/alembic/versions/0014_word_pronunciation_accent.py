"""add per-word pronunciation accent

Revision ID: 0014_word_pronunciation_accent
Revises: 0013_tts_chinese_voice
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = '0014_word_pronunciation_accent'
down_revision = '0013_tts_chinese_voice'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('word_items') and 'accent' not in {column['name'] for column in inspector.get_columns('word_items')}:
        op.add_column('word_items', sa.Column('accent', sa.String(length=2), nullable=False, server_default='us'))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('word_items') and 'accent' in {column['name'] for column in inspector.get_columns('word_items')}:
        op.drop_column('word_items', 'accent')
