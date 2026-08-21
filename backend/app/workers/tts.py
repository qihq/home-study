from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tts_asset import TtsAsset
from app.models.word_list import WordItem
from app.services.dictionary_audio import ensure_word_audio_asset
from app.services.mimo_speech import detect_language, resolve_voice
from app.services.mimo_tts import MimoTtsClient
from app.services.openai_tts import OpenAiTtsClient
from app.services.tts import tts_cache_key
from app.services.tts_config import api_key, get_tts_config
from app.workers.voice import generate_text_with_voice


def _voice_and_locale(config, language: str) -> tuple[str, str]:
    if config.protocol == 'mimo':
        voice = resolve_voice(config.voice, config.voice_zh, language)
        return voice, 'en-US' if language == 'en' else 'zh-CN'
    return config.voice, 'en-US'


def _tts_client(config, secret: str, voice: str):
    if config.protocol == 'mimo':
        return MimoTtsClient(secret, config.base_url, config.model, voice, config.speed)
    return OpenAiTtsClient(secret, config.base_url, config.model, voice, config.speed)


def generate_configured_tts(session: Session, text: str) -> Path:
    config = get_tts_config(session)
    if config is None or not config.api_key_encrypted:
        raise ValueError('TTS_NOT_CONFIGURED')
    language = detect_language(text)
    voice, locale = _voice_and_locale(config, language)
    key = tts_cache_key(text, locale, config.protocol, config.base_url, config.model, voice, config.speed)
    target = get_settings().tts_dir / locale / key[:2] / f'{key}.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        return target
    secret = api_key(config)
    partial = target.with_suffix('.wav.part')
    partial.write_bytes(_tts_client(config, secret, voice).synthesize(text))
    partial.replace(target)
    return target


def process_generate_tts(session: Session, word_item_id: str, report_progress=lambda _value: None) -> None:
    item = session.get(WordItem, word_item_id)
    if item is None:
        return
    settings = get_settings()
    config = get_tts_config(session)
    pronunciation_source = item.pronunciation_source if item.pronunciation_source != 'default' else (config.pronunciation_source if config is not None else 'configured')
    if pronunciation_source == 'custom' and config is not None and config.voice_version_id:
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
    if pronunciation_source != 'custom':
        # Single words prefer real dictionary audio over LLM-style TTS; falls back below on failure.
        dictionary_asset = ensure_word_audio_asset(session, item.display_text, item.source_language)
        if dictionary_asset is not None:
            item.tts_asset_id = dictionary_asset.id
            session.commit()
            return
    if config is None or not config.api_key_encrypted:
        return
    language = item.source_language if item.source_language in ('en', 'zh') else detect_language(item.display_text)
    voice, locale = _voice_and_locale(config, language)
    key = tts_cache_key(item.display_text, locale, config.protocol, config.base_url, config.model, voice, config.speed)
    existing = session.query(TtsAsset).filter_by(cache_key=key, status='ready').first()
    if existing is not None:
        item.tts_asset_id = existing.id
        session.commit()
        return
    secret = api_key(config)
    report_progress(25)
    audio = _tts_client(config, secret, voice).synthesize(item.display_text)
    report_progress(80)
    directory = settings.tts_dir / locale / key[:2]
    directory.mkdir(parents=True, exist_ok=True)
    partial = directory / f'{key}.wav.part'
    target = directory / f'{key}.wav'
    partial.write_bytes(audio)
    partial.replace(target)
    asset = TtsAsset(cache_key=key, provider=config.protocol, model=config.model, voice=voice, locale=locale, speed=config.speed, normalized_text=item.normalized_text, path=str(target))
    session.add(asset); session.flush()
    item.tts_asset_id = asset.id
    session.commit()


def regenerate_configured_item_tts(session: Session, item: WordItem) -> str:
    # Single words re-fetch real dictionary audio first; falls back to TTS below.
    dictionary_asset = ensure_word_audio_asset(session, item.display_text, item.source_language, regenerate=True)
    if dictionary_asset is not None:
        item.tts_asset_id = dictionary_asset.id
        session.commit()
        return dictionary_asset.id
    config = get_tts_config(session)
    if config is None or not config.api_key_encrypted:
        raise ValueError('TTS_NOT_CONFIGURED')
    language = item.source_language if item.source_language in ('en', 'zh') else detect_language(item.display_text)
    voice, locale = _voice_and_locale(config, language)
    secret = api_key(config)
    key = tts_cache_key(item.display_text, locale, config.protocol, config.base_url, config.model, voice, config.speed)
    directory = get_settings().tts_dir / locale / key[:2]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{key}.wav'
    partial = directory / f'{key}.wav.part'
    partial.write_bytes(_tts_client(config, secret, voice).synthesize(item.display_text))
    partial.replace(target)
    asset = session.query(TtsAsset).filter_by(cache_key=key).first()
    if asset is None:
        asset = TtsAsset(cache_key=key, provider=config.protocol, model=config.model, voice=voice, locale=locale, speed=config.speed, normalized_text=item.normalized_text, path=str(target))
        session.add(asset)
        session.flush()
    else:
        asset.path = str(target)
        asset.status = 'ready'
    item.tts_asset_id = asset.id
    session.commit()
    return asset.id
