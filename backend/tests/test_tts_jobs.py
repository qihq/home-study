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
