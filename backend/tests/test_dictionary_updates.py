import subprocess

import pytest


def _install(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('APP_LOCAL_DICTIONARY_PATH', str(tmp_path / 'dictionary.sqlite3'))
    from app.core.config import get_settings
    get_settings.cache_clear()


def test_enqueue_if_due_throttles_by_marker_and_respects_flag(session, monkeypatch, tmp_path) -> None:
    from app.models.job import Job
    from app.services import dictionary_updates as module

    _install(monkeypatch, tmp_path)

    first = module.enqueue_if_due(session)
    second = module.enqueue_if_due(session)

    assert first is not None
    assert second is None
    assert session.query(Job).filter_by(type='update_dictionary').count() == 1

    monkeypatch.setenv('APP_DICTIONARY_AUTO_UPDATE', 'false')
    from app.core.config import get_settings
    get_settings.cache_clear()
    assert module.enqueue_if_due(session) is None


def test_process_update_dictionary_builds_with_checksum_version_and_records_completion(session, monkeypatch, tmp_path) -> None:
    from app.services import dictionary_updates as module

    _install(monkeypatch, tmp_path)

    def fake_ensure(_path, filename, _url, _download, _cache_dir):
        return tmp_path / filename

    monkeypatch.setattr(module, 'ensure_source', fake_ensure)
    monkeypatch.setattr(module, 'checksum', lambda _path: 'a' * 64)
    calls = {}

    def fake_run(cmd, **kwargs):
        calls['cmd'] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, 'run', fake_run)

    module.process_update_dictionary(session, 'local')

    version = calls['cmd'][calls['cmd'].index('--version') + 1]
    assert version == f"auto-{'a' * 12}-{'a' * 12}"
    assert calls['cmd'][calls['cmd'].index('--output') + 1] == str(tmp_path / 'dictionary.sqlite3')
    assert (tmp_path / 'data' / 'dictionary-update.last').is_file()


def test_process_update_dictionary_raises_when_build_fails(session, monkeypatch, tmp_path) -> None:
    from app.services import dictionary_updates as module

    _install(monkeypatch, tmp_path)
    monkeypatch.setattr(module, 'ensure_source', lambda *_args, **_kwargs: tmp_path / 'ecdict.csv')
    monkeypatch.setattr(module, 'checksum', lambda _path: 'b' * 64)

    def failing(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr='builder exploded')

    monkeypatch.setattr(module.subprocess, 'run', failing)

    with pytest.raises(RuntimeError, match='DICTIONARY_UPDATE_FAILED'):
        module.process_update_dictionary(session, 'local')

    assert not (tmp_path / 'data' / 'dictionary-update.last').is_file()
