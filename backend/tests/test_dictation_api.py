from fastapi.testclient import TestClient


def test_dictation_session_requires_confirmed_word_list(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.post('/api/dictation-sessions', json={'word_list_version_id': 'missing', 'mode': 'ordered'}, headers=headers)

    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'WORD_LIST_VERSION_NOT_FOUND'


def test_dictation_session_returns_hidden_word_data_and_scores_result(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': '第一周', 'pasted_text': 'Apple\nbanana'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()

    created = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id'], 'mode': 'ordered'}, headers=headers)

    assert created.status_code == 201
    result = created.json()['results'][0]
    assert 'display_text' not in result
    scored = client.patch(f"/api/dictation-sessions/{created.json()['id']}/results/{result['id']}", json={'result': 'incorrect'}, headers=headers)
    assert scored.json()['result'] == 'incorrect'


def test_dictation_session_returns_optional_audio_asset_id(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': '第一周', 'pasted_text': 'Apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()

    created = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id'], 'mode': 'ordered'}, headers=headers)

    assert 'audio_asset_id' in created.json()['results'][0]
    assert 'word_item_id' in created.json()['results'][0]
    assert 'pronunciation_source' in created.json()['results'][0]


def test_dictation_can_persist_native_pronunciation_for_one_word(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': 'Ambiguous', 'pasted_text': 'use'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()
    created = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id']}, headers=headers).json()

    changed = client.patch(
        f"/api/dictation-sessions/{created['id']}/results/{created['results'][0]['id']}/pronunciation",
        json={'pronunciation_source': 'configured'}, headers=headers,
    )

    assert changed.status_code == 200
    assert changed.json()['pronunciation_source'] == 'configured'
    restored = client.get(f"/api/dictation-sessions/{created['id']}", headers=headers).json()
    assert restored['results'][0]['pronunciation_source'] == 'configured'


def test_dictation_can_force_regenerate_native_pronunciation(client: TestClient, admin_user, monkeypatch) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': 'Native retry', 'pasted_text': 'apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()
    created = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id']}, headers=headers).json()
    monkeypatch.setattr('app.api.dictation.regenerate_configured_item_tts', lambda _session, _item: 'new-native-asset')

    changed = client.patch(
        f"/api/dictation-sessions/{created['id']}/results/{created['results'][0]['id']}/pronunciation",
        json={'pronunciation_source': 'configured', 'regenerate': True}, headers=headers,
    )

    assert changed.status_code == 200
    assert changed.json() == {'pronunciation_source': 'configured', 'audio_asset_id': 'new-native-asset', 'regenerated': True}


def test_dictation_session_persists_and_returns_selected_voice_name_snapshots(client: TestClient, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='妈妈', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='清晰美音', status='ready')
        session.add(voice)
        session.commit()
        speaker_id, voice_id = speaker.id, voice.id
    word_list = client.post('/api/word-lists', json={'title': 'Voice week', 'pasted_text': 'apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()

    created = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id'], 'mode': 'ordered', 'speaker_profile_id': speaker_id, 'voice_version_id': voice_id}, headers=headers)

    assert created.status_code == 201
    restored = client.get(f"/api/dictation-sessions/{created.json()['id']}", headers=headers).json()
    assert restored['speaker_profile_name_snapshot'] == '妈妈'
    assert restored['voice_version_name_snapshot'] == '清晰美音'


def test_dictation_session_rejects_voice_from_different_selected_speaker(client: TestClient, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        selected_speaker = SpeakerProfile(display_name='Selected speaker', owner_user_id=owner.id)
        other_speaker = SpeakerProfile(display_name='Other speaker', owner_user_id=owner.id)
        session.add_all([selected_speaker, other_speaker])
        session.flush()
        other_voice = VoiceVersion(
            speaker_profile_id=other_speaker.id, display_name='Other voice', status='ready',
        )
        session.add(other_voice)
        session.commit()
        selected_speaker_id, other_voice_id = selected_speaker.id, other_voice.id
    word_list = client.post('/api/word-lists', json={'title': 'Voice week', 'pasted_text': 'apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()

    created = client.post('/api/dictation-sessions', json={
        'word_list_version_id': version['word_list_version_id'],
        'mode': 'ordered',
        'speaker_profile_id': selected_speaker_id,
        'voice_version_id': other_voice_id,
    }, headers=headers)

    assert created.status_code == 409
    assert created.json()['detail']['code'] == 'VOICE_VERSION_NOT_READY'


def test_dictation_session_rejects_non_ready_voice_for_selected_speaker(client: TestClient, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='Selected speaker', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='Pending voice', status='processing')
        session.add(voice)
        session.commit()
        speaker_id, voice_id = speaker.id, voice.id
    word_list = client.post('/api/word-lists', json={'title': 'Voice week', 'pasted_text': 'apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()

    created = client.post('/api/dictation-sessions', json={
        'word_list_version_id': version['word_list_version_id'],
        'mode': 'ordered',
        'speaker_profile_id': speaker_id,
        'voice_version_id': voice_id,
    }, headers=headers)

    assert created.status_code == 409
    assert created.json()['detail']['code'] == 'VOICE_VERSION_NOT_READY'


def test_dictation_session_returns_selected_voice_audio_asset(client: TestClient, admin_user, monkeypatch, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.tts_asset import TtsAsset
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='Voice owner', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(
            speaker_profile_id=speaker.id,
            display_name='Selected voice',
            status='ready',
            reference_audio_path=str(tmp_path / 'voice-reference.wav'),
            reference_sha256='a' * 64,
        )
        session.add(voice)
        session.commit()
        owner_id, speaker_id, voice_id = owner.id, speaker.id, voice.id

    audio_path = tmp_path / 'selected-voice.wav'
    audio_path.write_bytes(b'audio')
    monkeypatch.setattr(
        'app.api.dictation.generate_text_with_voice', lambda _session, _voice_id, _text: audio_path, raising=False,
    )

    word_list = client.post('/api/word-lists', json={'title': 'Voice week', 'pasted_text': 'apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()
    created = client.post('/api/dictation-sessions', json={
        'word_list_version_id': version['word_list_version_id'],
        'mode': 'ordered',
        'speaker_profile_id': speaker_id,
        'voice_version_id': voice_id,
    }, headers=headers)

    assert created.status_code == 201
    asset_id = created.json()['results'][0]['audio_asset_id']
    with get_session_factory()() as session:
        asset = session.get(TtsAsset, asset_id)
        assert asset is not None
        assert asset.voice == voice_id
        assert asset.owner_user_id == owner_id
    restored = client.get(f"/api/dictation-sessions/{created.json()['id']}", headers=headers)
    assert restored.json()['results'][0]['audio_asset_id'] == asset_id
