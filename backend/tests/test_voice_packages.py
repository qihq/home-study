import io
import zipfile

import pytest


def test_voice_package_encrypts_and_decrypts_manifest_and_audio() -> None:
    from app.services.voice_packages import create_voice_package, decrypt_voice_package

    package = create_voice_package(
        {'format_version': 1, 'speaker_profile_id': 'speaker-1'},
        {'audio/voice-1.wav': b'normalized-wav'},
        'correct password',
    )

    with zipfile.ZipFile(io.BytesIO(decrypt_voice_package(package, 'correct password'))) as archive:
        assert archive.read('manifest.json') == b'{"format_version":1,"speaker_profile_id":"speaker-1"}'
        assert archive.read('audio/voice-1.wav') == b'normalized-wav'


@pytest.mark.parametrize('password,tamper', [('wrong password', False), ('correct password', True)])
def test_voice_package_wrong_password_or_tampering_has_stable_error(password: str, tamper: bool) -> None:
    from app.services.voice_packages import VoicePackageError, create_voice_package, decrypt_voice_package

    package = bytearray(create_voice_package({'format_version': 1}, {'audio/voice.wav': b'wav'}, 'correct password'))
    if tamper:
        package[-1] ^= 1

    with pytest.raises(VoicePackageError, match='VOICE_PACKAGE_PASSWORD_INVALID'):
        decrypt_voice_package(bytes(package), password)


@pytest.mark.parametrize('name', ['../escape.wav', '/absolute.wav'])
def test_voice_package_rejects_zip_path_traversal(name: str) -> None:
    from app.services.voice_packages import VoicePackageError, create_voice_package, inspect_voice_package

    package = create_voice_package({'format_version': 1, 'voice_versions': []}, {name: b'wav'}, 'correct password')

    with pytest.raises(VoicePackageError, match='VOICE_PACKAGE_INVALID'):
        inspect_voice_package(io.BytesIO(package), 'correct password')


def test_voice_package_rejects_audio_hash_mismatch() -> None:
    from app.services.voice_packages import VoicePackageError, create_voice_package, inspect_voice_package

    package = create_voice_package(
        {'format_version': 1, 'voice_versions': [{'id': 'voice-1', 'reference_sha256': '0' * 64}]},
        {'audio/voice-1.wav': b'wav'}, 'correct password',
    )

    with pytest.raises(VoicePackageError, match='VOICE_PACKAGE_INVALID'):
        inspect_voice_package(io.BytesIO(package), 'correct password')


def test_staged_voice_import_uses_temp_plaintext_and_cleans_up(tmp_path, monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.voice_packages import create_voice_package, pop_staged_voice_package, stage_voice_package_import

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    package = create_voice_package({'format_version': 1, 'voice_versions': []}, {}, 'correct password')

    import_id, _preview = stage_voice_package_import(io.BytesIO(package), 'correct password')
    staged = pop_staged_voice_package(import_id)

    assert staged.plaintext_path.parent == get_settings().data_dir / 'imports' / 'voice'
    assert staged.plaintext_path.exists()
    staged.plaintext_path.unlink()
    get_settings.cache_clear()
