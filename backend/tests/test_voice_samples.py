import wave
from hashlib import sha256
from pathlib import Path

import pytest


def _wav(path: Path, duration_seconds: int) -> Path:
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        output.writeframes(b'\0\0' * 24_000 * duration_seconds)
    return path


def test_voice_sample_validation_accepts_wav_and_rejects_invalid_duration(tmp_path: Path) -> None:
    from app.services.voice_samples import VoiceSampleError, validate_normalized_wav

    valid = validate_normalized_wav(_wav(tmp_path / 'valid.wav', 8))
    assert valid.duration_ms == 8_000
    with pytest.raises(VoiceSampleError, match='VOICE_SAMPLE_TOO_SHORT'):
        validate_normalized_wav(_wav(tmp_path / 'short.wav', 2))
    with pytest.raises(VoiceSampleError, match='VOICE_SAMPLE_TOO_LONG'):
        validate_normalized_wav(_wav(tmp_path / 'long.wav', 31))


def test_voice_sample_validation_rejects_base64_over_ten_mb(tmp_path: Path, monkeypatch) -> None:
    from app.services.voice_samples import VoiceSampleError, validate_normalized_wav

    sample = _wav(tmp_path / 'sample.wav', 8)
    monkeypatch.setattr(Path, 'read_bytes', lambda _path: b'x' * 8_000_000)

    with pytest.raises(VoiceSampleError, match='VOICE_SAMPLE_BASE64_TOO_LARGE'):
        validate_normalized_wav(sample)


def test_voice_upload_requires_consent_and_enqueues_normalization(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    speaker = client.post('/api/speaker-profiles', json={'display_name': '爸爸'}, headers=headers).json()

    rejected = client.post(
        f"/api/speaker-profiles/{speaker['id']}/voice-versions/upload",
        files={'file': ('voice.wav', b'wav', 'audio/wav')}, data={'consent_confirmed': 'false'}, headers=headers,
    )
    accepted = client.post(
        f"/api/speaker-profiles/{speaker['id']}/voice-versions/upload",
        files={'file': ('voice.wav', b'wav', 'audio/wav')}, data={'consent_confirmed': 'true'}, headers=headers,
    )

    assert rejected.status_code == 422
    assert rejected.json()['detail']['code'] == 'VOICE_CONSENT_REQUIRED'
    assert accepted.status_code == 201
    assert accepted.json()['status'] == 'processing'


def test_normalizing_voice_sample_stores_normalized_audio_hash(monkeypatch, session, tmp_path: Path) -> None:
    from app.core.config import get_settings
    from app.models.speaker import VoiceVersion
    from app.services.speakers import create_speaker
    from app.services.voice_samples import VoiceSampleMetadata
    from app.workers.voice import process_normalize_voice_sample

    source = tmp_path / 'uploaded.wav'
    source.write_bytes(b'original-upload')
    speaker = create_speaker(session, 'Parent')
    voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='Reference', reference_audio_path=str(source))
    session.add(voice)
    session.commit()
    normalized_audio = b'normalized-audio'

    def fake_normalize(_source: Path, target: Path) -> VoiceSampleMetadata:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(normalized_audio)
        return VoiceSampleMetadata(duration_ms=8_000, size_bytes=len(normalized_audio))

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    monkeypatch.setattr('app.workers.voice.normalize_voice_sample', fake_normalize)

    process_normalize_voice_sample(session, voice.id)

    stored_voice = session.get(VoiceVersion, voice.id)
    assert stored_voice.reference_sha256 == sha256(normalized_audio).hexdigest()


def test_normalize_accepts_aac_recording_with_webm_filename(tmp_path: Path) -> None:
    import shutil
    import subprocess
    if shutil.which('ffmpeg') is None:
        pytest.skip('ffmpeg is required')
    from app.services.voice_samples import normalize_voice_sample

    source = tmp_path / 'browser-recording.webm'
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=8', '-c:a', 'aac', '-f', 'mp4', str(source)], check=True, capture_output=True)

    metadata = normalize_voice_sample(source, tmp_path / 'normalized.wav')

    assert metadata.duration_ms >= 7_900
