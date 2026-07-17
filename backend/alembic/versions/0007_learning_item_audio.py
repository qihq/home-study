"""add multi-speaker learning item audio cache

Revision ID: 0007_learning_item_audio
Revises: 0006_speaker_profiles
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = '0007_learning_item_audio'
down_revision = '0006_speaker_profiles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('learning_item_audio'):
        return
    op.create_table(
        'learning_item_audio',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('learning_item_id', sa.String(length=36), nullable=False),
        sa.Column('speaker_profile_id', sa.String(length=36), nullable=True),
        sa.Column('voice_version_id', sa.String(length=36), nullable=True),
        sa.Column('tts_asset_id', sa.String(length=36), nullable=False),
        sa.Column('config_fingerprint', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['learning_item_id'], ['word_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tts_asset_id'], ['tts_assets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('learning_item_id', 'config_fingerprint', name='uq_learning_item_audio_fingerprint'),
    )


def downgrade() -> None:
    op.drop_table('learning_item_audio')
