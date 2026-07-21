from fastapi.testclient import TestClient


def _install_local_dictionary(monkeypatch, tmp_path) -> None:
    import sqlite3
    from app.core.config import get_settings

    path = tmp_path / 'local-dictionary.sqlite3'
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE ecdict (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, definition TEXT, pos TEXT);
        CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY, word TEXT NOT NULL);
        CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        INSERT INTO metadata VALUES ('version', 'api-fixture-v1');
        INSERT INTO ecdict VALUES ('apple', '''æpl''', 'n. 苹果', 'a round fruit', 'n:100');
        INSERT INTO cedict VALUES ('苹果', '蘋果', 'ping2 guo3', 'apple/fruit');
    """)
    connection.commit(); connection.close()
    monkeypatch.setenv('APP_LOCAL_DICTIONARY_PATH', str(path))
    get_settings.cache_clear()


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


def test_dictionary_audio_regeneration_creates_new_asset_and_preserves_old_audio(client: TestClient, admin_user, monkeypatch, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models.dictionary import DictionaryEntry

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        entry = DictionaryEntry(
            query_hash='r' * 64,
            result_json='{"source_language":"en","source_text":"apple","primary_translation":"苹果"}',
        )
        session.add(entry); session.commit(); entry_id = entry.id

    generation = 0
    def generate(_session, _text):
        nonlocal generation
        generation += 1
        path = tmp_path / f'apple-{generation}.wav'
        path.write_bytes(f'wav-{generation}'.encode())
        return path

    monkeypatch.setattr('app.api.dictionary.generate_configured_tts', generate)
    first = client.post(f'/api/dictionary/entries/{entry_id}/audio', json={}, headers=headers)
    cached = client.post(f'/api/dictionary/entries/{entry_id}/audio', json={'regenerate': False}, headers=headers)
    regenerated = client.post(f'/api/dictionary/entries/{entry_id}/audio', json={'regenerate': True}, headers=headers)

    assert first.status_code == cached.status_code == regenerated.status_code == 200
    assert cached.json()['asset_id'] == first.json()['asset_id']
    assert regenerated.json()['asset_id'] != first.json()['asset_id']
    assert client.get(f"/api/tts-assets/{first.json()['asset_id']}/audio", headers=headers).content == b'wav-1'
    assert client.get(f"/api/tts-assets/{regenerated.json()['asset_id']}/audio", headers=headers).content == b'wav-2'


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


def test_local_english_and_chinese_words_work_without_ai_configuration(client: TestClient, admin_user, monkeypatch, tmp_path) -> None:
    _install_local_dictionary(monkeypatch, tmp_path)
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    english = client.post('/api/dictionary/lookup', json={'text': 'apple'}, headers=headers)
    chinese = client.post('/api/dictionary/lookup', json={'text': '苹果'}, headers=headers)
    repeated = client.post('/api/dictionary/lookup', json={'text': 'Apple'}, headers=headers)

    assert english.status_code == chinese.status_code == repeated.status_code == 200
    assert english.json()['primary_translation'] == '苹果'
    assert english.json()['parts_of_speech'] == [{'part': 'n.', 'meaning': '苹果'}]
    assert english.json()['result_source'] == 'ecdict'
    assert english.json()['source_attribution'] == 'ECDICT (MIT)'
    assert chinese.json()['primary_translation'] == 'apple'
    assert chinese.json()['result_source'] == 'cc-cedict'
    assert repeated.json()['cache_hit'] is True


def test_local_miss_without_ai_returns_specific_word_or_sentence_error(client: TestClient, admin_user, monkeypatch, tmp_path) -> None:
    _install_local_dictionary(monkeypatch, tmp_path)
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    word = client.post('/api/dictionary/lookup', json={'text': 'kumquat'}, headers=headers)
    sentence = client.post('/api/dictionary/lookup', json={'text': 'I like apples.'}, headers=headers)

    assert word.status_code == sentence.status_code == 409
    assert word.json()['detail']['code'] == 'DICTIONARY_LOCAL_MISS'
    assert sentence.json()['detail']['code'] == 'DICTIONARY_AI_REQUIRED'


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
