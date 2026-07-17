from pathlib import Path
import zipfile


def test_sqlite_backup_writes_copy_to_backup_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('APP_DATABASE_URL', f"sqlite:///{tmp_path / 'app.db'}")
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory
    get_settings.cache_clear(); get_engine.cache_clear(); get_session_factory.cache_clear()
    from app.db.base import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(get_engine())
    from app.services.backups import create_backup

    backup = create_backup()

    assert backup.is_file()
    assert backup.parent == get_settings().backups_dir
    with zipfile.ZipFile(backup) as archive:
        assert archive.namelist() == ['app.db']


def test_backup_includes_existing_reference_audio_and_encryption_keys(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('APP_DATABASE_URL', f"sqlite:///{tmp_path / 'app.db'}")
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory
    get_settings.cache_clear(); get_engine.cache_clear(); get_session_factory.cache_clear()
    from app.db.base import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(get_engine())
    settings = get_settings()
    reference = settings.data_dir / 'voice-samples' / 'reference.wav'
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b'reference-audio')
    (settings.data_dir / 'ai-settings.key').write_bytes(b'ai-key')
    (settings.data_dir / 'tts-settings.key').write_bytes(b'tts-key')
    from app.models.speaker import SpeakerProfile, VoiceVersion
    with get_session_factory()() as session:
        speaker = SpeakerProfile(display_name='Parent')
        session.add(speaker); session.flush()
        session.add(VoiceVersion(speaker_profile_id=speaker.id, display_name='Reference', reference_audio_path=str(reference)))
        session.commit()
    from app.services.backups import create_backup

    backup = create_backup()

    with zipfile.ZipFile(backup) as archive:
        assert sorted(archive.namelist()) == ['ai-settings.key', 'app.db', 'reference-audio/reference.wav', 'tts-settings.key']


def test_backups_created_in_the_same_second_have_distinct_archive_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('APP_DATABASE_URL', f"sqlite:///{tmp_path / 'app.db'}")
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory
    get_settings.cache_clear(); get_engine.cache_clear(); get_session_factory.cache_clear()
    from app.db.base import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(get_engine())
    from app.services.backups import create_backup

    first = create_backup()
    second = create_backup()

    assert first != second
    assert first.is_file()
    assert second.is_file()
