import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _create_legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE word_items (
                id VARCHAR(36) PRIMARY KEY,
                word_list_version_id VARCHAR(36) NOT NULL,
                position INTEGER NOT NULL,
                display_text VARCHAR(160) NOT NULL,
                normalized_text VARCHAR(160) NOT NULL,
                source_location TEXT,
                warning_json TEXT,
                tts_asset_id VARCHAR(36)
            );
            INSERT INTO word_items (id, word_list_version_id, position, display_text, normalized_text)
            VALUES ('item-1', 'version-1', 0, 'Apple', 'apple');
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version (version_num) VALUES ('0001_initial');
        """)


def test_existing_word_item_is_migrated_as_english_word(tmp_path: Path) -> None:
    database = tmp_path / 'legacy.db'
    _create_legacy_database(database)
    environment = {**os.environ, 'APP_DATA_DIR': str(tmp_path / 'data'), 'APP_DATABASE_URL': f'sqlite:///{database}'}

    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=Path(__file__).parents[1], env=environment, check=True)

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            'SELECT item_type, source_language, target_language FROM word_items WHERE id = ?', ('item-1',)
        ).fetchone()
    assert row == ('word', 'en', 'zh')


def test_migration_creates_a_pre_upgrade_sqlite_backup(tmp_path: Path) -> None:
    database = tmp_path / 'legacy.db'
    _create_legacy_database(database)
    data_dir = tmp_path / 'data'
    environment = {**os.environ, 'APP_DATA_DIR': str(data_dir), 'APP_DATABASE_URL': f'sqlite:///{database}'}

    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=Path(__file__).parents[1], env=environment, check=True)

    backups = list((data_dir / 'backups').glob('pre-0002-*.db'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute('SELECT display_text FROM word_items WHERE id = ?', ('item-1',)).fetchone() == ('Apple',)


def test_sentence_normalization_preserves_punctuation() -> None:
    from app.services.learning_items import infer_item_type, normalize_learning_text

    assert normalize_learning_text('  I   like apples.  ', 'en') == 'i like apples.'
    assert infer_item_type('I like apples.', 'en') == 'sentence'


def test_learning_models_keep_legacy_names_as_aliases() -> None:
    from sqlalchemy import Text

    from app.models.learning_item import LearningItem, LearningList, LearningListVersion
    from app.models.word_list import WordItem, WordList, WordListVersion

    assert WordItem is LearningItem
    assert WordList is LearningList
    assert WordListVersion is LearningListVersion
    assert isinstance(LearningItem.__table__.c.display_text.type, Text)
    assert isinstance(LearningItem.__table__.c.normalized_text.type, Text)
