import hashlib
import json
import unicodedata
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tts_asset import TtsAsset
AUDIO_VERSION = 3


def _normalize_text(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', text).strip().split()).casefold()


def tts_cache_key(text: str, locale: str, protocol: str, base_url: str, model: str, voice: str, speed: float) -> str:
    payload = {'protocol': protocol, 'base_url': base_url.rstrip('/'), 'model': model, 'audio_version': AUDIO_VERSION, 'text': _normalize_text(text), 'locale': locale, 'voice': voice, 'speed': speed, 'format': 'wav'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ensure_tts_asset(session: Session, synthesize: Callable[[str], bytes], *, text: str, locale: str, voice: str, speed: float, protocol: str = 'mimo', base_url: str = '', model: str = 'configured') -> TtsAsset:
    key = tts_cache_key(text, locale, protocol, base_url, model, voice, speed)
    existing = session.scalar(select(TtsAsset).where(TtsAsset.cache_key == key, TtsAsset.status == 'ready'))
    if existing is not None:
        return existing
    audio = synthesize(text)
    output = get_settings().tts_dir / locale / key[:2]
    output.mkdir(parents=True, exist_ok=True)
    partial = output / f'{key}.mp3.part'; final = output / f'{key}.mp3'
    partial.write_bytes(audio); partial.replace(final)
    asset = TtsAsset(cache_key=key, provider=protocol, model=model, locale=locale, voice=voice, speed=speed, normalized_text=_normalize_text(text), path=str(final))
    session.add(asset); session.commit(); session.refresh(asset)
    return asset
