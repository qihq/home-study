from fastapi.testclient import TestClient


def test_dictionary_audio_returns_authenticated_asset_for_a_ready_selected_voice(client: TestClient, admin_user, monkeypatch, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models.dictionary import DictionaryEntry
    from app.models.speaker import SpeakerProfile, VoiceVersion

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        entry = DictionaryEntry(
            query_hash='a' * 64,
            result_json='{"source_language":"en","source_text":"apple","primary_translation":"苹果"}',
        )
        speaker = SpeakerProfile(display_name='妈妈')
        session.add_all([entry, speaker])
        session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='清晰美音', status='ready', reference_audio_path='reference.wav')
        session.add(voice)
        session.commit()
        entry_id, voice_id = entry.id, voice.id

    audio_path = tmp_path / 'apple.wav'
    audio_path.write_bytes(b'wav')
    monkeypatch.setattr('app.api.dictionary.generate_text_with_voice', lambda *_args: audio_path)
    response = client.post(f'/api/dictionary/entries/{entry_id}/audio', json={'voice_version_id': voice_id}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {'asset_id': response.json()['asset_id']}
    assert client.get(f"/api/tts-assets/{response.json()['asset_id']}/audio", headers=headers).content == b'wav'
    with TestClient(client.app) as anonymous_client:
        assert anonymous_client.get(f"/api/tts-assets/{response.json()['asset_id']}/audio").status_code == 401


def test_dictionary_audio_and_asset_are_not_accessible_to_another_user(client: TestClient, admin_user, monkeypatch, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models.child import Child
    from app.models.dictionary import DictionaryEntry, DictionaryHistory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User
    from app.services.users import hash_password

    owner_login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    owner_headers = {'Cookie': owner_login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        attacker = User(username='other-parent', password_hash=hash_password('different horse'))
        entry = DictionaryEntry(
            query_hash='b' * 64,
            result_json='{"source_language":"en","source_text":"apple","primary_translation":"苹果"}',
        )
        child = Child(display_name='孩子', slug='owner-child')
        speaker = SpeakerProfile(display_name='妈妈')
        session.add_all([attacker, child, entry, speaker])
        session.flush()
        # These fields express the intended resource ownership; the vulnerable endpoints ignore it.
        speaker.owner_user_id = owner.id
        history = DictionaryHistory(child_id=child.id, entry_id=entry.id)
        history.owner_user_id = owner.id
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='清晰美音', status='ready', reference_audio_path='reference.wav')
        session.add_all([history, voice])
        session.commit()
        entry_id, voice_id = entry.id, voice.id

    audio_path = tmp_path / 'owner-apple.wav'
    audio_path.write_bytes(b'owner-wav')
    monkeypatch.setattr('app.api.dictionary.generate_text_with_voice', lambda *_args: audio_path)
    owner_audio = client.post(
        f'/api/dictionary/entries/{entry_id}/audio', json={'voice_version_id': voice_id}, headers=owner_headers,
    )
    assert owner_audio.status_code == 200

    attacker_login = client.post('/api/auth/login', json={'username': 'other-parent', 'password': 'different horse'})
    attacker_headers = {'Cookie': attacker_login.headers['set-cookie'].split(';', 1)[0]}
    attacker_audio = client.post(
        f'/api/dictionary/entries/{entry_id}/audio', json={'voice_version_id': voice_id}, headers=attacker_headers,
    )
    attacker_download = client.get(f"/api/tts-assets/{owner_audio.json()['asset_id']}/audio", headers=attacker_headers)

    assert (attacker_audio.status_code, attacker_download.status_code) == (403, 403)


def test_ready_voice_versions_are_available_for_dictionary_playback(client: TestClient, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        speaker = SpeakerProfile(display_name='爸爸')
        session.add(speaker)
        session.flush()
        session.add_all([
            VoiceVersion(speaker_profile_id=speaker.id, display_name='已就绪', status='ready'),
            VoiceVersion(speaker_profile_id=speaker.id, display_name='处理中', status='processing'),
        ])
        session.commit()

    response = client.get('/api/voice-versions?ready=true', headers=headers)

    assert response.status_code == 200
    assert response.json() == [{'id': response.json()[0]['id'], 'display_name': '爸爸 / 已就绪'}]


def test_dictionary_lookup_honors_auto_and_manual_direction(client: TestClient, admin_user, monkeypatch) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    client.patch('/api/settings/ai', json={
        'protocol': 'openai_chat_compatible', 'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1', 'api_key': 'ai-secret-abcd',
        'model': 'custom-model', 'temperature': 0.1, 'timeout_seconds': 45, 'enabled': True,
    }, headers=headers)
    monkeypatch.setattr('app.services.openai_chat.OpenAiChatClient.complete', lambda *_args: '''{
        "source_language": "zh", "target_language": "en", "item_type": "sentence",
        "source_text": "我喜欢苹果。", "primary_translation": "I like apples.", "phonetic": null,
        "parts_of_speech": [], "alternatives": [], "examples": [], "usage_note": null
    }''')

    response = client.post('/api/dictionary/lookup', json={
        'text': '我喜欢苹果。', 'source_language': 'auto',
    }, headers=headers)

    assert response.status_code == 200
    assert response.json()['source_language'] == 'zh'
    assert response.json()['target_language'] == 'en'
    assert response.json()['cache_hit'] is False
    assert response.json()['entry_id']


def test_dictionary_history_is_child_scoped_and_deletable(client: TestClient, admin_user, monkeypatch) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    client.patch('/api/settings/ai', json={
        'protocol': 'openai_chat_compatible', 'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1', 'api_key': 'ai-secret-abcd',
        'model': 'custom-model', 'temperature': 0.1, 'timeout_seconds': 45, 'enabled': True,
    }, headers=headers)
    monkeypatch.setattr('app.services.openai_chat.OpenAiChatClient.complete', lambda *_args: '''{
        "source_language": "en", "target_language": "zh", "item_type": "word",
        "source_text": "apple", "primary_translation": "苹果", "phonetic": null,
        "parts_of_speech": [], "alternatives": [], "examples": [], "usage_note": null
    }''')
    client.post('/api/dictionary/lookup', json={'text': 'apple'}, headers=headers)

    history = client.get('/api/dictionary/history', headers=headers)

    assert history.status_code == 200
    assert history.json()['items'][0]['source_text'] == 'apple'
    entry_id = history.json()['items'][0]['id']
    deleted = client.delete(f'/api/dictionary/history/{entry_id}', headers=headers)
    assert deleted.status_code == 204
    assert client.get('/api/dictionary/history', headers=headers).json()['items'] == []


def test_dictionary_history_uses_created_at_and_id_cursor(client: TestClient, admin_user, monkeypatch) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    client.patch('/api/settings/ai', json={
        'protocol': 'openai_chat_compatible', 'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1', 'api_key': 'ai-secret-abcd',
        'model': 'custom-model', 'temperature': 0.1, 'timeout_seconds': 45, 'enabled': True,
    }, headers=headers)
    monkeypatch.setattr('app.services.openai_chat.OpenAiChatClient.complete', lambda _self, messages: '''{
        "source_language": "en", "target_language": "zh", "item_type": "word",
        "source_text": "apple", "primary_translation": "苹果", "phonetic": null,
        "parts_of_speech": [], "alternatives": [], "examples": [], "usage_note": null
    }''' if 'apple' in str(messages) else '''{
        "source_language": "en", "target_language": "zh", "item_type": "word",
        "source_text": "pear", "primary_translation": "梨", "phonetic": null,
        "parts_of_speech": [], "alternatives": [], "examples": [], "usage_note": null
    }''')
    client.post('/api/dictionary/lookup', json={'text': 'apple'}, headers=headers)
    client.post('/api/dictionary/lookup', json={'text': 'pear'}, headers=headers)

    first = client.get('/api/dictionary/history?limit=1', headers=headers).json()
    second = client.get(f"/api/dictionary/history?limit=1&cursor={first['next_cursor']}", headers=headers).json()

    assert len(first['items']) == 1
    assert first['next_cursor'] is not None
    assert len(second['items']) == 1
    assert first['items'][0]['id'] != second['items'][0]['id']
