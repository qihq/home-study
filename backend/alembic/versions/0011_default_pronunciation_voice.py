"""add default pronunciation voice selection

Revision ID: 0011_default_pronunciation_voice
Revises: 0010_recording_title
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = '0011_default_pronunciation_voice'
down_revision = '0010_recording_title'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('tts_provider_config'):
        return
    names = {column['name'] for column in inspector.get_columns('tts_provider_config')}
    if 'pronunciation_source' not in names:
        op.add_column('tts_provider_config', sa.Column('pronunciation_source', sa.String(length=20), nullable=False, server_default='configured'))
    if 'voice_version_id' not in names:
        op.add_column('tts_provider_config', sa.Column('voice_version_id', sa.String(length=36), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('tts_provider_config'):
        return
    names = {column['name'] for column in inspector.get_columns('tts_provider_config')}
    if 'voice_version_id' in names:
        op.drop_column('tts_provider_config', 'voice_version_id')
    if 'pronunciation_source' in names:
        op.drop_column('tts_provider_config', 'pronunciation_source')
