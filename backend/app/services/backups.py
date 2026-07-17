import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.speaker import VoiceVersion


def create_backup() -> Path:
    settings = get_settings()
    if not settings.database_url.startswith('sqlite:///'):
        raise ValueError('BACKUP_DATABASE_UNSUPPORTED')
    source_path = Path(settings.database_url.removeprefix('sqlite:///'))
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    database_copy = settings.backups_dir / f'.app-{timestamp}.db'
    target = settings.backups_dir / f'app-{timestamp}.zip'
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(database_copy)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    try:
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(database_copy, 'app.db')
            for audio_path in _reference_audio_paths(settings.data_dir):
                archive.write(audio_path, f'reference-audio/{audio_path.name}')
            for key_name in ('ai-settings.key', 'tts-settings.key'):
                key_path = settings.data_dir / key_name
                if key_path.is_file():
                    archive.write(key_path, key_name)
    finally:
        database_copy.unlink(missing_ok=True)
    return target


def _reference_audio_paths(data_dir: Path) -> list[Path]:
    with get_session_factory()() as session:
        paths = session.scalars(select(VoiceVersion.reference_audio_path).where(VoiceVersion.reference_audio_path.is_not(None))).all()
    resolved_data_dir = data_dir.resolve()
    return [path for value in paths if (path := Path(value)).is_file() and resolved_data_dir in path.resolve().parents]
