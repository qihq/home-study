from datetime import datetime, timedelta, timezone


def _install_settings(monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()


def _make_asset(session, tmp_path, key: str, age_days: int):
    from app.models.tts_asset import TtsAsset

    path = tmp_path / 'data' / 'tts' / key[:2] / f'{key}.wav'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'wav')
    asset = TtsAsset(
        cache_key=key, provider='mimo', model='mimo-v2.5-tts', voice='Chloe',
        locale='en-US', speed=1.0, normalized_text=key, path=str(path),
    )
    asset.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset, path


def test_cleanup_deletes_only_stale_unreferenced_assets(session, monkeypatch, tmp_path) -> None:
    from app.models.child import Child
    from app.models.learning_item import LearningItem
    from app.models.learning_item_audio import LearningItemAudio
    from app.models.tts_asset import TtsAsset
    from app.services import tts_maintenance as module
    from app.services.words import create_draft_word_list

    _install_settings(monkeypatch, tmp_path)
    stale_unreferenced, stale_path = _make_asset(session, tmp_path, 'a' * 64, 120)
    stale_item_referenced, _ = _make_asset(session, tmp_path, 'b' * 64, 120)
    fresh_unreferenced, fresh_path = _make_asset(session, tmp_path, 'c' * 64, 10)
    stale_audio_referenced, _ = _make_asset(session, tmp_path, 'd' * 64, 120)

    child = Child(display_name='孩子', slug='cleanup-child')
    session.add(child); session.commit()
    create_draft_word_list(session, child.id, 'cleanup', [{'display_text': 'apple', 'normalized_text': 'apple'}])
    item = session.query(LearningItem).first()
    item.tts_asset_id = stale_item_referenced.id
    session.add(LearningItemAudio(learning_item_id=item.id, voice_version_id=None, tts_asset_id=stale_audio_referenced.id, config_fingerprint='f' * 64))
    session.commit()

    result = module.maybe_cleanup_stale_tts_assets(session)

    assert result == {'skipped': False, 'deleted_assets': 1, 'deleted_files': 1}
    assert session.get(TtsAsset, stale_unreferenced.id) is None
    assert stale_path.exists() is False
    assert session.get(TtsAsset, fresh_unreferenced.id) is not None
    assert fresh_path.exists() is True
    assert session.get(TtsAsset, stale_item_referenced.id) is not None
    assert session.get(TtsAsset, stale_audio_referenced.id) is not None


def test_cleanup_runs_at_most_once_per_interval(session, monkeypatch, tmp_path) -> None:
    from app.models.tts_asset import TtsAsset
    from app.services import tts_maintenance as module

    _install_settings(monkeypatch, tmp_path)
    _make_asset(session, tmp_path, 'e' * 64, 120)
    marker = tmp_path / 'data' / 'tts-cleanup.last'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(datetime.now(timezone.utc).isoformat())

    result = module.maybe_cleanup_stale_tts_assets(session)

    assert result == {'skipped': True, 'deleted_assets': 0, 'deleted_files': 0}
    assert session.query(TtsAsset).count() == 1


def test_cleanup_never_raises_on_missing_paths(session, monkeypatch, tmp_path) -> None:
    from app.models.tts_asset import TtsAsset
    from app.services import tts_maintenance as module

    _install_settings(monkeypatch, tmp_path)
    asset = TtsAsset(
        cache_key='f' * 64, provider='mimo', model='mimo-v2.5-tts', voice='Chloe',
        locale='en-US', speed=1.0, normalized_text='gone', path=str(tmp_path / 'missing.wav'),
    )
    asset.created_at = datetime.now(timezone.utc) - timedelta(days=200)
    session.add(asset); session.commit()

    result = module.maybe_cleanup_stale_tts_assets(session)

    assert result == {'skipped': False, 'deleted_assets': 1, 'deleted_files': 0}
    assert session.query(TtsAsset).count() == 0


def test_cleanup_enforces_capacity_cap_with_oldest_unreferenced_first(session, monkeypatch, tmp_path) -> None:
    from app.models.tts_asset import TtsAsset
    from app.services import tts_maintenance as module

    _install_settings(monkeypatch, tmp_path)
    monkeypatch.setenv('APP_TTS_MAX_ASSETS', '1')
    from app.core.config import get_settings
    get_settings.cache_clear()
    oldest, _ = _make_asset(session, tmp_path, '1' * 64, 30)
    newer, _ = _make_asset(session, tmp_path, '2' * 64, 20)
    newest, _ = _make_asset(session, tmp_path, '3' * 64, 10)

    result = module.maybe_cleanup_stale_tts_assets(session)

    assert result['deleted_assets'] == 2
    assert session.get(TtsAsset, oldest.id) is None
    assert session.get(TtsAsset, newer.id) is None
    assert session.get(TtsAsset, newest.id) is not None
