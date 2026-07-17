"""add speaker profiles and voice versions

Revision ID: 0006_speaker_profiles
Revises: 0005_unknown_items
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = '0006_speaker_profiles'
down_revision = '0005_unknown_items'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('speaker_profiles'):
        return
    op.create_table(
        'speaker_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('avatar_color', sa.String(length=30), nullable=False),
        sa.Column('default_voice_version_id', sa.String(length=36), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'voice_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('speaker_profile_id', sa.String(length=36), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('reference_audio_path', sa.Text(), nullable=True),
        sa.Column('reference_mime_type', sa.String(length=50), nullable=True),
        sa.Column('reference_sha256', sa.String(length=64), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('style_instruction', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('failure_code', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['speaker_profile_id'], ['speaker_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('voice_versions')
    op.drop_table('speaker_profiles')
