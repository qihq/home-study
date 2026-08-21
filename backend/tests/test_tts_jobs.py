def test_confirmed_word_list_enqueues_tts_job_for_each_word_when_configured(session) -> None:
    from app.models.child import Child
    from app.models.job import Job
    from app.services.words import confirm_word_list, create_draft_word_list

    from app.services.tts_config import save_tts_config
    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='tts-child'); session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, 'test', [{'display_text': 'apple', 'normalized_text': 'apple'}, {'display_text': 'banana', 'normalized_text': 'banana'}])

    confirm_word_list(session, word_list.id)

    assert session.query(Job).filter_by(type='generate_tts').count() == 2


def test_configuring_tts_later_queues_audio_for_existing_confirmed_english_items(session) -> None:
    from app.models.child import Child
    from app.models.job import Job
    from app.services.learning_items import enqueue_missing_tts_for_confirmed_items
    from app.services.tts_config import save_tts_config
    from app.services.words import confirm_word_list, create_draft_word_list

    child = Child(display_name='Later TTS', slug='later-tts-child')
    session.add(child)
    session.commit()
    word_list = create_draft_word_list(session, child.id, 'test', [
        {'display_text': 'apple', 'normalized_text': 'apple'},
        {'display_text': '你好', 'normalized_text': '你好', 'source_language': 'zh'},
    ])
    confirm_word_list(session, word_list.id)
    assert session.query(Job).filter_by(type='generate_tts').count() == 0

    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)

    assert enqueue_missing_tts_for_confirmed_items(session) == 1
    assert session.query(Job).filter_by(type='generate_tts').count() == 1


def test_generate_tts_job_prefers_dictionary_audio_for_single_words(session, monkeypatch, tmp_path) -> None:
    from app.models.child import Child
    from app.models.tts_asset import TtsAsset
    from app.services.tts_config import save_tts_config
    from app.services.words import confirm_word_list, create_draft_word_list
    from app.workers.tts import process_generate_tts

    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='dict-audio-child'); session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, 'dict audio', [{'display_text': 'apple', 'normalized_text': 'apple'}])
    version = confirm_word_list(session, word_list.id)
    item = version.items[0]

    audio_file = tmp_path / 'apple.mp3'
    audio_file.write_bytes(b'ID3' + b'\x00' * 60 + b'mp3')

    def fake_ensure(session, text, source_language, **_kwargs):
        asset = TtsAsset(
            cache_key='d' * 64, provider='dictionary_audio', model='dictvoice', voice='us',
            locale='en-US', speed=1.0, normalized_text=text, path=str(audio_file),
        )
        session.add(asset); session.commit(); session.refresh(asset)
        return asset

    monkeypatch.setattr('app.workers.tts.ensure_word_audio_asset', fake_ensure)

    process_generate_tts(session, item.id)

    session.refresh(item)
    assert item.tts_asset_id is not None
    assert session.get(TtsAsset, item.tts_asset_id).provider == 'dictionary_audio'


def test_audio_version_upgrade_requeues_existing_word_audio(session) -> None:
    from app.models.child import Child
    from app.models.job import Job
    from app.models.tts_asset import TtsAsset
    from app.services.learning_items import enqueue_missing_tts_for_confirmed_items
    from app.services.tts_config import save_tts_config
    from app.services.words import confirm_word_list, create_draft_word_list

    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='refresh-audio'); session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, 'test', [{'display_text': 'use', 'normalized_text': 'use'}])
    version = confirm_word_list(session, word_list.id)
    job = session.query(Job).filter_by(type='generate_tts').one(); session.delete(job)
    old = TtsAsset(cache_key='old-cache-key', provider='mimo', model='mimo-v2.5-tts', voice='Chloe', locale='en-US', speed=1.0, normalized_text='use', path='/old.wav')
    session.add(old); session.flush(); version.items[0].tts_asset_id = old.id; session.commit()

    assert enqueue_missing_tts_for_confirmed_items(session) == 1
    session.refresh(version.items[0])
    assert version.items[0].tts_asset_id is None
    assert session.query(Job).filter_by(type='generate_tts', entity_id=version.items[0].id, status='queued').count() == 1


def test_dictionary_audio_asset_with_stale_version_is_requeued(session, monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings
    from app.models.child import Child
    from app.models.job import Job
    from app.models.tts_asset import TtsAsset
    from app.services.learning_items import enqueue_missing_tts_for_confirmed_items
    from app.services.tts_config import save_tts_config
    from app.services.words import confirm_word_list, create_draft_word_list

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='stale-dict-audio'); session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, 'test', [{'display_text': 'apple', 'normalized_text': 'apple'}])
    version = confirm_word_list(session, word_list.id)
    job = session.query(Job).filter_by(type='generate_tts').one(); session.delete(job)
    stale = TtsAsset(cache_key='s' * 64, provider='dictionary_audio', model='dictvoice', voice='us', locale='en-US', speed=1.0, normalized_text='apple', path='/old.mp3')
    session.add(stale); session.flush(); version.items[0].tts_asset_id = stale.id; session.commit()

    assert enqueue_missing_tts_for_confirmed_items(session) == 1
    session.refresh(version.items[0])
    assert version.items[0].tts_asset_id is None
    assert session.query(Job).filter_by(type='generate_tts', entity_id=version.items[0].id, status='queued').count() == 1


def test_dictionary_audio_asset_with_current_version_is_kept(session, monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings
    from app.models.child import Child
    from app.models.job import Job
    from app.models.tts_asset import TtsAsset
    from app.services.dictionary_audio import dictionary_asset_cache_key
    from app.services.learning_items import enqueue_missing_tts_for_confirmed_items
    from app.services.tts_config import save_tts_config
    from app.services.words import confirm_word_list, create_draft_word_list

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='fresh-dict-audio'); session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, 'test', [{'display_text': 'apple', 'normalized_text': 'apple'}])
    version = confirm_word_list(session, word_list.id)
    job = session.query(Job).filter_by(type='generate_tts').one(); session.delete(job)
    fresh = TtsAsset(
        cache_key=dictionary_asset_cache_key('apple', 'us', 'shared'), provider='dictionary_audio',
        model='dictionaryapi.dev', voice='us', locale='en-US', speed=1.0, normalized_text='apple', path='/new.mp3',
    )
    session.add(fresh); session.flush(); version.items[0].tts_asset_id = fresh.id; session.commit()

    assert enqueue_missing_tts_for_confirmed_items(session) == 0
    session.refresh(version.items[0])
    assert version.items[0].tts_asset_id == fresh.id
    assert session.query(Job).filter_by(type='generate_tts', entity_id=version.items[0].id, status='queued').count() == 0


def test_dictionary_audio_upgrade_requeues_legacy_tts_word_audio_once(session, monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings
    from app.models.child import Child
    from app.models.job import Job
    from app.models.tts_asset import TtsAsset
    from app.services.learning_items import enqueue_dictionary_audio_upgrade, enqueue_missing_tts_for_confirmed_items
    from app.services.tts import tts_cache_key
    from app.services.tts_config import save_tts_config
    from app.services.words import confirm_word_list, create_draft_word_list

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='upgrade-audio-child'); session.add(child); session.commit()
    word_list = create_draft_word_list(session, child.id, 'test', [{'display_text': 'use', 'normalized_text': 'use'}])
    version = confirm_word_list(session, word_list.id)
    job = session.query(Job).filter_by(type='generate_tts').one(); session.delete(job)
    key = tts_cache_key('use', 'en-US', 'mimo', 'https://api.xiaomimimo.com/v1', 'mimo-v2.5-tts', 'Chloe', 1.0)
    legacy = TtsAsset(cache_key=key, provider='mimo', model='mimo-v2.5-tts', voice='Chloe', locale='en-US', speed=1.0, normalized_text='use', path='/old.wav')
    session.add(legacy); session.flush(); version.items[0].tts_asset_id = legacy.id; session.commit()

    # a TTS asset matching the configured fingerprint is stable (no loop)
    assert enqueue_missing_tts_for_confirmed_items(session) == 0
    # the one-time upgrade re-enqueues it once so generation can prefer dictionary audio
    assert enqueue_dictionary_audio_upgrade(session) == 1
    session.refresh(version.items[0])
    assert version.items[0].tts_asset_id is None
    assert session.query(Job).filter_by(type='generate_tts', entity_id=version.items[0].id, status='queued').count() == 1
    # the marker file makes the upgrade a no-op on later cycles
    assert enqueue_dictionary_audio_upgrade(session) == 0
    assert session.query(Job).filter_by(type='generate_tts', entity_id=version.items[0].id, status='queued').count() == 1
