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
        'model': 'tts-1', 'voice': 'alloy', 'speed': 1.2,
        'pronunciation_source': 'configured', 'voice_version_id': None,
        'api_key_configured': True, 'api_key_mask': '********-key',
    }


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
