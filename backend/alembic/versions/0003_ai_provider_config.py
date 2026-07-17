"""add independent dictionary AI configuration

Revision ID: 0003_ai_provider_config
Revises: 0002_learning_dictionary_voice_profiles
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = '0003_ai_provider_config'
down_revision = '0002_learning_dictionary_voice_profiles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('ai_provider_config'):
        return
    op.create_table(
        'ai_provider_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=200), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('ai_provider_config')
