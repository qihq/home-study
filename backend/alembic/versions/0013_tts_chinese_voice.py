"""add Chinese TTS voice to provider config

Revision ID: 0013_tts_chinese_voice
Revises: 0012_word_pronunciation_source
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = '0013_tts_chinese_voice'
down_revision = '0012_word_pronunciation_source'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('tts_provider_config') and 'voice_zh' not in {column['name'] for column in inspector.get_columns('tts_provider_config')}:
        op.add_column('tts_provider_config', sa.Column('voice_zh', sa.String(length=200), nullable=False, server_default=''))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('tts_provider_config') and 'voice_zh' in {column['name'] for column in inspector.get_columns('tts_provider_config')}:
        op.drop_column('tts_provider_config', 'voice_zh')
