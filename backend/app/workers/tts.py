from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tts_asset import TtsAsset
from app.models.word_list import WordItem
from app.services.mimo_tts import MimoTtsClient
from app.services.openai_tts import OpenAiTtsClient
from app.services.tts import tts_cache_key
from app.services.tts_config import api_key, get_tts_config
from app.workers.voice import generate_text_with_voice


def generate_configured_tts(session: Session, text: str) -> Path:
    config = get_tts_config(session)
    if config is None or not config.api_key_encrypted:
        raise ValueError('TTS_NOT_CONFIGURED')
    key = tts_cache_key(text, 'en-US', config.protocol, config.base_url, config.model, config.voice, config.speed)
    target = get_settings().tts_dir / 'en-US' / key[:2] / f'{key}.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        return target
    secret = api_key(config)
    client = MimoTtsClient(secret, config.base_url, config.model, config.voice) if config.protocol == 'mimo' else OpenAiTtsClient(secret, config.base_url, config.model, config.voice, config.speed)
    partial = target.with_suffix('.wav.part')
    partial.write_bytes(client.synthesize(text))
    partial.replace(target)
    return target


def process_generate_tts(session: Session, word_item_id: str, report_progress=lambda _value: None) -> None:
    item = session.get(WordItem, word_item_id)
    if item is None:
        return
    settings = get_settings()
    config = get_tts_config(session)
    if config is None or (config.pronunciation_source != 'custom' and not config.api_key_encrypted):
        return
    pronunciation_source = item.pronunciation_source if item.pronunciation_source != 'default' else config.pronunciation_source
    if pronunciation_source == 'custom' and config.voice_version_id:
        report_progress(25)
        target = generate_text_with_voice(session, config.voice_version_id, item.display_text)
        report_progress(80)
        from app.workers.voice import VOICE_AUDIO_VERSION
        key = tts_cache_key(item.display_text, 'en-US', f'custom-v{VOICE_AUDIO_VERSION}', '', '', config.voice_version_id, 1.0)
        existing = session.query(TtsAsset).filter_by(cache_key=key, status='ready').first()
        if existing is None:
            existing = TtsAsset(cache_key=key, provider='mimo_voiceclone', model='custom', voice=config.voice_version_id, locale='en-US', speed=1.0, normalized_text=item.normalized_text, path=str(target))
            session.add(existing); session.flush()
        item.tts_asset_id = existing.id
        session.commit()
        return
    key = tts_cache_key(item.display_text, 'en-US', config.protocol, config.base_url, config.model, config.voice, config.speed)
    existing = session.query(TtsAsset).filter_by(cache_key=key, status='ready').first()
    if existing is not None:
        item.tts_asset_id = existing.id
        session.commit()
        return
    secret = api_key(config)
    client = MimoTtsClient(secret, config.base_url, config.model, config.voice) if config.protocol == 'mimo' else OpenAiTtsClient(secret, config.base_url, config.model, config.voice, config.speed)
    report_progress(25)
    audio = client.synthesize(item.display_text)
    report_progress(80)
    directory = settings.tts_dir / 'en-US' / key[:2]
    directory.mkdir(parents=True, exist_ok=True)
    partial = directory / f'{key}.wav.part'
    target = directory / f'{key}.wav'
    partial.write_bytes(audio)
    partial.replace(target)
    asset = TtsAsset(cache_key=key, provider=config.protocol, model=config.model, voice=config.voice, locale='en-US', speed=config.speed, normalized_text=item.normalized_text, path=str(target))
    session.add(asset); session.flush()
    item.tts_asset_id = asset.id
    session.commit()


def regenerate_configured_item_tts(session: Session, item: WordItem) -> str:
    config = get_tts_config(session)
    if config is None or not config.api_key_encrypted:
        raise ValueError('TTS_NOT_CONFIGURED')
    secret = api_key(config)
    client = MimoTtsClient(secret, config.base_url, config.model, config.voice) if config.protocol == 'mimo' else OpenAiTtsClient(secret, config.base_url, config.model, config.voice, config.speed)
    key = tts_cache_key(item.display_text, 'en-US', config.protocol, config.base_url, config.model, config.voice, config.speed)
    directory = get_settings().tts_dir / 'en-US' / key[:2]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{key}.wav'
    partial = directory / f'{key}.wav.part'
    partial.write_bytes(client.synthesize(item.display_text))
    partial.replace(target)
    asset = session.query(TtsAsset).filter_by(cache_key=key).first()
    if asset is None:
        asset = TtsAsset(cache_key=key, provider=config.protocol, model=config.model, voice=config.voice, locale='en-US', speed=config.speed, normalized_text=item.normalized_text, path=str(target))
        session.add(asset)
        session.flush()
    else:
        asset.path = str(target)
        asset.status = 'ready'
    item.tts_asset_id = asset.id
    session.commit()
    return asset.id
