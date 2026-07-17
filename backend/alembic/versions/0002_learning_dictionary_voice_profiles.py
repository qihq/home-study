"""add unified learning-item and dictation snapshot fields

Revision ID: 0002_learning_dictionary_voice_profiles
Revises: 0001_initial
Create Date: 2026-07-13
"""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from alembic import op
import sqlalchemy as sa

from app.core.config import get_settings


revision = '0002_learning_dictionary_voice_profiles'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def _backup_sqlite_database() -> None:
    """Create a readable pre-migration copy before changing the SQLite schema."""
    bind = op.get_bind()
    database_path = bind.engine.url.database
    if bind.dialect.name != 'sqlite' or database_path in (None, ':memory:'):
        return

    backups_dir = get_settings().backups_dir
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = backups_dir / f'pre-0002-{timestamp}.db'
    with sqlite3.connect(Path(database_path)) as source, sqlite3.connect(destination) as target:
        source.backup(target)


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    _backup_sqlite_database()

    word_item_columns = _column_names('word_items')
    with op.batch_alter_table('word_items') as batch_op:
        if 'item_type' not in word_item_columns:
            batch_op.add_column(sa.Column('item_type', sa.String(length=20), nullable=True))
        if 'source_language' not in word_item_columns:
            batch_op.add_column(sa.Column('source_language', sa.String(length=10), nullable=True))
        if 'target_language' not in word_item_columns:
            batch_op.add_column(sa.Column('target_language', sa.String(length=10), nullable=True))
        if 'translation_text' not in word_item_columns:
            batch_op.add_column(sa.Column('translation_text', sa.Text(), nullable=True))
        if 'dictionary_entry_id' not in word_item_columns:
            batch_op.add_column(sa.Column('dictionary_entry_id', sa.String(length=36), nullable=True))

    op.execute("UPDATE word_items SET item_type = 'word', source_language = 'en', target_language = 'zh'")

    with op.batch_alter_table('word_items') as batch_op:
        batch_op.alter_column('item_type', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('source_language', existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column('target_language', existing_type=sa.String(length=10), nullable=False)

    if _table_exists('dictation_sessions'):
        session_columns = _column_names('dictation_sessions')
        with op.batch_alter_table('dictation_sessions') as batch_op:
            if 'speaker_profile_id' not in session_columns:
                batch_op.add_column(sa.Column('speaker_profile_id', sa.String(length=36), nullable=True))
            if 'voice_version_id' not in session_columns:
                batch_op.add_column(sa.Column('voice_version_id', sa.String(length=36), nullable=True))
            if 'speaker_profile_name_snapshot' not in session_columns:
                batch_op.add_column(sa.Column('speaker_profile_name_snapshot', sa.String(length=100), nullable=True))
            if 'voice_version_name_snapshot' not in session_columns:
                batch_op.add_column(sa.Column('voice_version_name_snapshot', sa.String(length=100), nullable=True))

    if _table_exists('dictation_results'):
        result_columns = _column_names('dictation_results')
        with op.batch_alter_table('dictation_results') as batch_op:
            if 'item_type_snapshot' not in result_columns:
                batch_op.add_column(sa.Column('item_type_snapshot', sa.String(length=20), nullable=True))
        op.execute("UPDATE dictation_results SET item_type_snapshot = 'word'")
        with op.batch_alter_table('dictation_results') as batch_op:
            batch_op.alter_column('item_type_snapshot', existing_type=sa.String(length=20), nullable=False)


def downgrade() -> None:
    raise NotImplementedError('Restore the pre-0002 SQLite backup instead of deleting migrated data.')
