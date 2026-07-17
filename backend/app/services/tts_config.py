import base64
import hashlib
import hmac
import secrets
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tts_provider_config import TtsProviderConfig


def _key_path():
    path = get_settings().data_dir / 'tts-settings.key'
    if not path.exists():
        path.write_bytes(secrets.token_bytes(32))
    return path


def _stream(key: bytes, nonce: bytes, size: int) -> bytes:
    blocks = []
    for counter in range((size + 31) // 32):
        blocks.append(hmac.digest(key, b'enc' + nonce + counter.to_bytes(4, 'big'), 'sha256'))
    return b''.join(blocks)[:size]


def _encrypt(value: str) -> str:
    key, plaintext = _key_path().read_bytes(), value.encode()
    nonce = secrets.token_bytes(16)
    ciphertext = bytes(left ^ right for left, right in zip(plaintext, _stream(key, nonce, len(plaintext))))
    tag = hmac.digest(key, b'mac' + nonce + ciphertext, 'sha256')
    return base64.urlsafe_b64encode(b'v1' + nonce + tag + ciphertext).decode()


def _decrypt(value: str) -> str:
    decoded = base64.urlsafe_b64decode(value.encode())
    version, nonce, tag, ciphertext = decoded[:2], decoded[2:18], decoded[18:50], decoded[50:]
    if version != b'v1' or not hmac.compare_digest(tag, hmac.digest(_key_path().read_bytes(), b'mac' + nonce + ciphertext, 'sha256')):
        raise ValueError('TTS_SECRET_DECRYPT_FAILED')
    return bytes(left ^ right for left, right in zip(ciphertext, _stream(_key_path().read_bytes(), nonce, len(ciphertext)))).decode()


def get_tts_config(session: Session) -> TtsProviderConfig | None:
    return session.get(TtsProviderConfig, 1)


def api_key(config: TtsProviderConfig) -> str | None:
    return _decrypt(config.api_key_encrypted) if config.api_key_encrypted else None


def mask_key(key: str | None) -> str | None:
    if not key:
        return None
    return f'********{key[-4:]}' if len(key) >= 4 else '********'


def save_tts_config(session: Session, *, protocol: str, base_url: str, api_key_value: str | None, model: str, voice: str, speed: float, pronunciation_source: str = 'configured', voice_version_id: str | None = None) -> TtsProviderConfig:
    config = get_tts_config(session)
    if config is None:
        config = TtsProviderConfig(id=1, protocol=protocol, base_url=base_url, model=model, voice=voice, speed=speed)
        session.add(config)
    else:
        config.protocol, config.base_url, config.model, config.voice, config.speed = protocol, base_url, model, voice, speed
    if api_key_value:
        config.api_key_encrypted = _encrypt(api_key_value)
    config.pronunciation_source = pronunciation_source
    config.voice_version_id = voice_version_id if pronunciation_source == 'custom' else None
    session.commit()
    session.refresh(config)
    return config
