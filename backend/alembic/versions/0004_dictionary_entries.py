"""add dictionary cache and child-scoped history

Revision ID: 0004_dictionary_entries
Revises: 0003_ai_provider_config
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = '0004_dictionary_entries'
down_revision = '0003_ai_provider_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('dictionary_entries'):
        return
    op.create_table(
        'dictionary_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('query_hash', sa.String(length=64), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hit_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('query_hash'),
    )
    op.create_table(
        'dictionary_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('child_id', sa.String(length=36), nullable=False),
        sa.Column('entry_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['child_id'], ['children.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entry_id'], ['dictionary_entries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('dictionary_history')
    op.drop_table('dictionary_entries')
