import base64
import logging
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _login_headers(client: TestClient) -> dict[str, str]:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    return {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}


def _ready_voice(client: TestClient, tmp_path: Path) -> tuple[str, str]:
    from app.db.session import get_session_factory
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.models.user import User

    reference = tmp_path / 'private-reference.wav'
    reference.write_bytes(b'private-reference-audio')
    with get_session_factory()() as session:
        owner = session.query(User).filter_by(username='parent').one()
        speaker = SpeakerProfile(display_name='Parent', owner_user_id=owner.id)
        session.add(speaker)
        session.flush()
        voice = VoiceVersion(
            speaker_profile_id=speaker.id,
            display_name='Private reference',
            status='ready',
            reference_audio_path=str(reference),
            reference_sha256=sha256(reference.read_bytes()).hexdigest(),
        )
        session.add(voice)
        session.commit()
        return speaker.id, voice.id


@pytest.mark.parametrize('path', ['/api/settings/ai', '/api/settings/tts'])
def test_anonymous_requests_cannot_read_configuration(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401


def test_anonymous_requests_cannot_preview_ready_reference_audio_or_export_voice_package(client: TestClient, admin_user, tmp_path: Path) -> None:
    speaker_id, voice_id = _ready_voice(client, tmp_path)

    preview = client.get(f'/api/voice-versions/{voice_id}/preview')
    exported = client.post(
        f'/api/speaker-profiles/{speaker_id}/export',
        json={'password': 'voice-export-password-for-test', 'voice_version_ids': [voice_id]},
    )

    assert preview.status_code == 401
    assert exported.status_code == 401


def test_request_and_error_logs_do_not_disclose_voice_secrets(client: TestClient, admin_user, tmp_path: Path, monkeypatch, caplog: pytest.LogCaptureFixture) -> None:
    from app.services.mimo_voice_clone import MimoVoiceCloneClient, MimoVoiceCloneError
    from app.services.openai_chat import OpenAiChatError

    api_key = 'security-test-api-key-9f3a'
    export_password = 'security-test-export-password-7c2b'
    reference = tmp_path / 'voice-reference.wav'
    reference.write_bytes(b'voice-reference-for-log-check')
    voice_base64_prefix = base64.b64encode(reference.read_bytes()).decode()[:16]
    headers = _login_headers(client)
    speaker_id, _voice_id = _ready_voice(client, tmp_path)
    caplog.set_level(logging.DEBUG)

    saved = client.patch('/api/settings/ai', headers=headers, json={
        'protocol': 'openai_chat_compatible',
        'display_name': 'Security test provider',
        'base_url': 'https://provider.example/v1',
        'api_key': api_key,
        'model': 'security-test-model',
        'temperature': 0.1,
        'timeout_seconds': 45,
        'enabled': True,
    })
    monkeypatch.setattr(
        'app.services.openai_chat.OpenAiChatClient.complete',
        lambda *_args: (_ for _ in ()).throw(OpenAiChatError('AI_REQUEST_FAILED')),
    )
    connection_error = client.post('/api/settings/ai/test', headers=headers)
    export_error = client.post(
        f'/api/speaker-profiles/{speaker_id}/export',
        headers=headers,
        json={'password': export_password, 'voice_version_ids': ['missing-voice-version']},
    )
    monkeypatch.setattr('app.services.mimo_voice_clone.urlopen', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('upstream unavailable')))

    with pytest.raises(MimoVoiceCloneError):
        MimoVoiceCloneClient(api_key, 'https://provider.example/v1').synthesize(
            'apple', reference, 'Read clearly.',
        )

    assert saved.status_code == 200
    assert connection_error.status_code == 502
    assert export_error.status_code == 422
    assert api_key not in caplog.text
    assert export_password not in caplog.text
    assert voice_base64_prefix not in caplog.text


def test_voice_sample_path_is_not_a_static_download_url(tmp_path: Path, monkeypatch) -> None:
    from app.core.config import get_settings

    frontend = tmp_path / 'frontend-dist'
    frontend.mkdir()
    (frontend / 'index.html').write_text('<div>Family Learning</div>', encoding='utf-8')
    data_dir = tmp_path / 'data'
    sample = data_dir / 'voice-samples' / 'private.wav'
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b'private-reference-audio')
    monkeypatch.setenv('APP_DATA_DIR', str(data_dir))
    monkeypatch.setenv('APP_DATABASE_URL', f"sqlite:///{tmp_path / 'app.db'}")
    monkeypatch.setenv('APP_FRONTEND_DIR', str(frontend))
    get_settings.cache_clear()
    from app.db.session import get_engine, get_session_factory

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    from app.main import create_app

    response = TestClient(create_app()).get('/voice-samples/private.wav')

    assert response.status_code == 404
