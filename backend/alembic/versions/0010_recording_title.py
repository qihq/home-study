"""add editable recording title

Revision ID: 0010_recording_title
Revises: 0009_spelling_ocr_config
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = '0010_recording_title'
down_revision = '0009_spelling_ocr_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('recordings'):
        return
    names = {column['name'] for column in inspector.get_columns('recordings')}
    if 'title' not in names:
        op.add_column('recordings', sa.Column('title', sa.String(length=160), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('recordings') and 'title' in {column['name'] for column in inspector.get_columns('recordings')}:
        op.drop_column('recordings', 'title')
