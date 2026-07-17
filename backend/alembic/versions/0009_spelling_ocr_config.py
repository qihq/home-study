"""add configurable spelling image recognition provider

Revision ID: 0009_spelling_ocr_config
Revises: 0008_user_owned_voice_audio
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = '0009_spelling_ocr_config'
down_revision = '0008_user_owned_voice_audio'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('spelling_ocr_config'):
        return
    op.create_table(
        'spelling_ocr_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('protocol', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=200), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('spelling_ocr_config')
