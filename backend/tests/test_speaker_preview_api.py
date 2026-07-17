from fastapi.testclient import TestClient


def test_ready_voice_preview_requires_owner_and_returns_audio(client: TestClient, admin_user, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User
    from app.services.users import hash_password

    owner_login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    owner_headers = {'Cookie': owner_login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='妈妈', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='清晰美音', status='ready')
        session.add(voice)
        session.commit()
        voice_id = voice.id
    from app.core.config import get_settings
    preview = get_settings().tts_dir / 'voice-previews' / f'{voice_id}.wav'
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_bytes(b'wav')

    response = client.get(f'/api/voice-versions/{voice_id}/preview', headers=owner_headers)

    assert response.status_code == 200
    assert response.content == b'wav'
