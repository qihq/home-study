from fastapi.testclient import TestClient


def test_voice_version_list_exposes_selection_metadata_only_when_requested(client: TestClient, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='Mother', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='Clear US English', status='ready')
        session.add(voice)
        session.commit()
        voice_id = voice.id

    legacy_response = client.get('/api/voice-versions?ready=true', headers=headers)
    selection_response = client.get(
        '/api/voice-versions?ready=true&include_selection_metadata=true', headers=headers,
    )

    assert legacy_response.status_code == 200
    assert legacy_response.json() == [{'id': voice_id, 'display_name': 'Mother / Clear US English'}]
    assert selection_response.status_code == 200
    assert selection_response.json() == [{
        'id': voice_id,
        'speaker_profile_id': speaker.id,
        'display_name': 'Mother / Clear US English',
        'status': 'ready',
    }]


def test_listing_speakers_creates_an_owned_default_profile_when_none_exists(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.get('/api/speaker-profiles', headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['display_name'] == '我的声音'
