def test_tts_settings_masks_api_key_and_retains_it_when_omitted(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';')[0]}
    saved = client.patch('/api/settings/tts', headers=headers, json={
        'protocol': 'mimo',
        'base_url': 'https://api.xiaomimimo.com/v1',
        'api_key': 'secret-api-key',
        'model': 'mimo-v2.5-tts',
        'voice': 'Chloe',
        'speed': 1.0,
    })
    assert saved.status_code == 200
    assert 'secret-api-key' not in saved.text

    retained = client.patch('/api/settings/tts', headers=headers, json={
        'protocol': 'openai_compatible',
        'base_url': 'https://tts.example.com/v1',
        'model': 'tts-1',
        'voice': 'alloy',
        'speed': 1.2,
    })
    assert retained.status_code == 200
    body = client.get('/api/settings/tts', headers=headers).json()
    assert body == {
        'protocol': 'openai_compatible', 'base_url': 'https://tts.example.com/v1',
        'model': 'tts-1', 'voice': 'alloy', 'voice_zh': '冰糖', 'speed': 1.2,
        'pronunciation_source': 'configured', 'voice_version_id': None,
        'api_key_configured': True, 'api_key_mask': '********-key',
    }


def test_tts_settings_save_chinese_voice_for_mimo(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';')[0]}

    saved = client.patch('/api/settings/tts', headers=headers, json={
        'protocol': 'mimo', 'base_url': 'https://api.xiaomimimo.com/v1', 'api_key': 'key',
        'model': 'mimo-v2.5-tts', 'voice': 'Milo', 'voice_zh': '苏打', 'speed': 0.8,
    })

    assert saved.status_code == 200
    body = saved.json()
    assert body['voice'] == 'Milo'
    assert body['voice_zh'] == '苏打'


def test_tts_settings_reject_deprecated_mimo_v2_models(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';')[0]}

    response = client.patch('/api/settings/tts', headers=headers, json={
        'protocol': 'mimo', 'base_url': 'https://api.xiaomimimo.com/v1', 'api_key': 'key',
        'model': 'mimo-v2-tts', 'voice': 'Chloe', 'speed': 1.0,
    })

    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'TTS_MODEL_DEPRECATED'


def test_tts_settings_reject_unknown_mimo_model_and_invalid_voices(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';')[0]}
    base = {'protocol': 'mimo', 'base_url': 'https://api.xiaomimimo.com/v1', 'api_key': 'key', 'model': 'mimo-v2.5-tts', 'voice': 'Chloe', 'speed': 1.0}

    unknown_model = client.patch('/api/settings/tts', headers=headers, json={**base, 'model': 'mimo-v3-tts'})
    assert unknown_model.status_code == 422
    assert unknown_model.json()['detail']['code'] == 'TTS_MODEL_UNKNOWN'

    bad_en_voice = client.patch('/api/settings/tts', headers=headers, json={**base, 'voice': 'custom-voice'})
    assert bad_en_voice.status_code == 422
    assert bad_en_voice.json()['detail']['code'] == 'TTS_VOICE_INVALID'

    bad_zh_voice = client.patch('/api/settings/tts', headers=headers, json={**base, 'voice_zh': '自定义'})
    assert bad_zh_voice.status_code == 422
    assert bad_zh_voice.json()['detail']['code'] == 'TTS_VOICE_INVALID'


def test_tts_settings_skip_official_validation_for_custom_mimo_gateway(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';')[0]}

    response = client.patch('/api/settings/tts', headers=headers, json={
        'protocol': 'mimo', 'base_url': 'https://tts.example.com/v1', 'api_key': 'key',
        'model': 'my-custom-mimo-model', 'voice': 'my-voice', 'speed': 1.0,
    })

    assert response.status_code == 200
    assert response.json()['model'] == 'my-custom-mimo-model'


def test_cache_key_changes_when_tts_protocol_or_model_changes():
    from app.services.tts import tts_cache_key

    mimo = tts_cache_key('apple', 'en-US', 'mimo', 'https://api.xiaomimimo.com/v1', 'mimo-v2.5-tts', 'Chloe', 1.0)
    openai = tts_cache_key('apple', 'en-US', 'openai_compatible', 'https://tts.example.com/v1', 'tts-1', 'Chloe', 1.0)

    assert mimo != openai


def test_tts_settings_can_select_a_ready_owned_cloned_voice(client, admin_user):
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';')[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='Mother', owner_user_id=owner.id)
        session.add(speaker); session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='Clear', status='ready')
        session.add(voice); session.commit()
        voice_id = voice.id

    saved = client.patch('/api/settings/tts', headers=headers, json={
        'protocol': 'mimo', 'base_url': 'https://api.xiaomimimo.com/v1', 'api_key': 'key',
        'model': 'mimo-v2.5-tts', 'voice': 'Chloe', 'speed': 1.0,
        'pronunciation_source': 'custom', 'voice_version_id': voice_id,
    })

    assert saved.status_code == 200
    assert saved.json()['pronunciation_source'] == 'custom'
    assert saved.json()['voice_version_id'] == voice_id
    assert client.get('/api/settings/tts', headers=headers).json()['voice_version_id'] == voice_id
