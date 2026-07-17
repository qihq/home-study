"""add child-scoped unknown items

Revision ID: 0005_unknown_items
Revises: 0004_dictionary_entries
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = '0005_unknown_items'
down_revision = '0004_dictionary_entries'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('unknown_items'):
        return
    op.create_table(
        'unknown_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('child_id', sa.String(length=36), nullable=False),
        sa.Column('dictionary_entry_id', sa.String(length=36), nullable=True),
        sa.Column('item_type', sa.String(length=20), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=False),
        sa.Column('source_language', sa.String(length=10), nullable=False),
        sa.Column('target_language', sa.String(length=10), nullable=False),
        sa.Column('translation_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('marked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('mastered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['children.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dictionary_entry_id'], ['dictionary_entries.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_unknown_items_active', 'unknown_items',
        ['child_id', 'source_language', 'target_language', 'normalized_text'],
        unique=True, sqlite_where=sa.text("status = 'unknown'"),
    )


def downgrade() -> None:
    op.drop_table('unknown_items')
