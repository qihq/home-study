import base64
import json


def test_voice_clone_sends_reference_audio_as_data_uri(monkeypatch, tmp_path) -> None:
    from app.services.mimo_voice_clone import MimoVoiceCloneClient

    sample = tmp_path / 'sample.wav'
    sample.write_bytes(b'wav-bytes')
    captured = {}

    def fake_urlopen(request, timeout):
        captured['url'] = request.full_url
        captured['headers'] = {key.casefold(): value for key, value in request.header_items()}
        captured['payload'] = request.data

        class Response:
            def read(self):
                return ('{"choices":[{"message":{"audio":{"data":"' + base64.b64encode(b'preview').decode() + '"}}}]}').encode()
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return Response()

    monkeypatch.setattr('app.services.mimo_voice_clone.urlopen', fake_urlopen)

    audio = MimoVoiceCloneClient('test-key', 'https://api.example/v1').synthesize('apple', sample, 'Read clearly')

    assert audio == b'preview'
    assert captured['url'] == 'https://api.example/v1/chat/completions'
    assert captured['headers']['api-key'] == 'test-key'
    assert b'"model":"mimo-v2.5-tts-voiceclone"' in captured['payload']
    assert b'"voice":"data:audio/wav;base64,d2F2LWJ5dGVz"' in captured['payload']
    payload = json.loads(captured['payload'])
    assert payload['messages'] == [
        {'role': 'system', 'content': 'Read clearly\nSpeak only the assistant content once.'},
        {'role': 'assistant', 'content': 'apple'},
    ]
    assert 'translate' not in str(payload['messages']).lower()


def test_voice_preview_marks_version_ready(monkeypatch, session, tmp_path) -> None:
    from app.models.speaker import VoiceVersion
    from app.services.speakers import create_speaker
    from app.workers.voice import process_voice_preview

    wav = tmp_path / 'sample.wav'
    wav.write_bytes(b'wav-bytes')
    speaker = create_speaker(session, '爸爸')
    voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='原声', reference_audio_path=str(wav), status='processing')
    session.add(voice)
    session.commit()
    monkeypatch.setattr('app.workers.voice.MimoVoiceCloneClient.synthesize', lambda *_args: b'preview-audio')
    monkeypatch.setenv('APP_MIMO_API_KEY', 'test-key')
    monkeypatch.setenv('APP_MIMO_API_BASE_URL', 'https://api.example/v1')
    from app.core.config import get_settings
    get_settings.cache_clear()

    process_voice_preview(session, voice.id)

    assert session.get(VoiceVersion, voice.id).status == 'ready'


def test_ready_voice_generates_arbitrary_text_wav(monkeypatch, session, tmp_path) -> None:
    from app.models.speaker import VoiceVersion
    from app.services.speakers import create_speaker
    from app.workers.voice import generate_text_with_voice

    wav = tmp_path / 'sample.wav'
    wav.write_bytes(b'wav-bytes')
    speaker = create_speaker(session, '妈妈')
    voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='原声', reference_audio_path=str(wav), status='ready')
    session.add(voice)
    session.commit()
    monkeypatch.setattr('app.workers.voice.MimoVoiceCloneClient.synthesize', lambda *_args: b'generated-audio')
    monkeypatch.setenv('APP_MIMO_API_KEY', 'test-key')
    monkeypatch.setenv('APP_MIMO_API_BASE_URL', 'https://api.example/v1')
    from app.core.config import get_settings
    get_settings.cache_clear()

    audio_path = generate_text_with_voice(session, voice.id, 'I like apples.')

    assert audio_path.read_bytes() == b'generated-audio'


def test_voice_preview_uses_mimo_credentials_saved_in_settings(monkeypatch, session, tmp_path) -> None:
    from app.models.speaker import VoiceVersion
    from app.services.speakers import create_speaker
    from app.services.tts_config import save_tts_config
    from app.workers.voice import process_voice_preview
    from app.core.config import get_settings

    monkeypatch.delenv('APP_MIMO_API_KEY', raising=False)
    monkeypatch.delenv('APP_MIMO_API_BASE_URL', raising=False)
    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    save_tts_config(session, protocol='mimo', base_url='https://saved.example/v1', api_key_value='saved-key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    wav = tmp_path / 'sample.wav'; wav.write_bytes(b'wav-bytes')
    speaker = create_speaker(session, '妈妈')
    voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='原声', reference_audio_path=str(wav), status='processing')
    session.add(voice); session.commit()
    captured = {}
    monkeypatch.setattr('app.workers.voice.MimoVoiceCloneClient.__init__', lambda self, key, url: captured.update(key=key, url=url))
    monkeypatch.setattr('app.workers.voice.MimoVoiceCloneClient.synthesize', lambda *_args: b'preview-audio')

    process_voice_preview(session, voice.id)

    assert captured == {'key': 'saved-key', 'url': 'https://saved.example/v1'}
    assert session.get(VoiceVersion, voice.id).status == 'ready'
