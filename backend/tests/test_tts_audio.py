from pathlib import Path


def test_tts_audio_is_not_public(client, admin_user, tmp_path: Path) -> None:
    from app.db.session import get_session_factory
    from app.models.tts_asset import TtsAsset

    with get_session_factory()() as session:
        audio = tmp_path / 'word.wav'; audio.write_bytes(b'wav')
        asset = TtsAsset(cache_key='x', voice='Chloe', locale='en-US', speed=1.0, normalized_text='apple', path=str(audio))
        session.add(asset); session.commit(); asset_id = asset.id

    assert client.get(f'/api/tts-assets/{asset_id}/audio').status_code == 401


def test_tts_stream_endpoint_streams_wav_chunks(client, admin_user, monkeypatch) -> None:
    from app.db.session import get_session_factory
    from app.services.tts_config import save_tts_config

    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    with get_session_factory()() as session:
        save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    monkeypatch.setattr('app.api.tts.MimoTtsClient.stream', lambda self, text: iter([b'pcm-chunk']))

    response = client.get('/api/tts/stream', params={'text': 'I like apples.'}, headers=headers)

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('audio/wav')
    assert response.content.startswith(b'RIFF')
    assert response.content.endswith(b'pcm-chunk')


def test_tts_stream_requires_mimo_configuration(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.get('/api/tts/stream', params={'text': 'hello'}, headers=headers)

    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'TTS_NOT_CONFIGURED'
