import base64
import json
import re
import threading
from datetime import datetime
from hashlib import sha256
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_resource_owner, require_user
from app.core.config import get_settings
from app.models.child import Child
from app.models.dictionary import DictionaryEntry, DictionaryHistory
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.models.tts_asset import TtsAsset
from app.models.user import User
from app.services.ai_config import ai_api_key, get_ai_config
from app.services.dictionary import DictionaryServiceError, delete_dictionary_history, detect_direction, dictionary_history, lookup_dictionary, store_dictionary_result
from app.services.dictionary_audio import ensure_word_audio_asset, prefetch_word_audio
from app.services.local_dictionary import LocalDictionary
from app.services.online_dictionary import lookup_online_word
from app.services.openai_chat import OpenAiChatClient, OpenAiChatError
from app.workers.tts import generate_configured_tts
from app.workers.voice import generate_text_with_voice
from app.services.tts_config import get_tts_config
from app.services.tts import AUDIO_VERSION

router = APIRouter(tags=['dictionary'])

# Interactive playback must not stall on unreachable sources; the worker path
# keeps the longer default timeout.
INTERACTIVE_FETCH_TIMEOUT = 5.0


class DictionaryLookupRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    source_language: Literal['auto', 'en', 'zh'] = 'auto'


class DictionaryAudioRequest(BaseModel):
    voice_version_id: str | None = None
    regenerate: bool = False
    accent: Literal['uk', 'us'] = 'us'
    source: Literal['default', 'native', 'configured', 'custom'] = 'default'


def _start_audio_prefetch(text: str, source_language: str) -> None:
    """Fill the disk cache for a looked-up word so play is instant.

    Runs detached and never raises; the play endpoint simply finds the cached
    file afterwards. Network calls happen in the thread, not the request.
    """
    def worker() -> None:
        try:
            prefetch_word_audio(text, source_language)
        except Exception:
            pass

    threading.Thread(target=worker, name=f'dict-audio-prefetch:{text[:20]}', daemon=True).start()


def _current_child(session: DbSession) -> Child:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        child = Child(display_name='Child', slug='default-child')
        session.add(child)
        session.flush()
    return child


@router.post('/dictionary/lookup')
def lookup(payload: DictionaryLookupRequest, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    source, target = detect_direction(payload.text) if payload.source_language == 'auto' else (payload.source_language, 'en' if payload.source_language == 'zh' else 'zh')
    normalized = payload.text.strip()
    local_eligible = bool(re.fullmatch(r"[A-Za-z][A-Za-z'’-]*", normalized)) if source == 'en' else bool(re.fullmatch(r'[\u3400-\u9fff]{1,12}', normalized))
    local_dictionary = LocalDictionary(get_settings().local_dictionary_path)
    if local_eligible:
        local = local_dictionary.lookup(normalized, source)
        if local is not None:
            attribution = 'ECDICT (MIT)' if local.source == 'ecdict' else 'CC-CEDICT (CC BY-SA 3.0)'
            result = local.result.model_copy(update={'result_source': local.source, 'source_attribution': attribution})
            found = store_dictionary_result(
                session, _current_child(session).id, normalized, source, target, local_dictionary.fingerprint,
                result, prompt_version='local-v2', owner_user_id=user.id,
            )
            _prefetch_word_audio(result)
            return {**found.result.model_dump(), 'cache_hit': found.cache_hit, 'entry_id': found.entry_id}
    if source == 'en' and local_eligible:
        # Free online dictionary tier for English words (30-day cached), below the LLM tier.
        online = lookup_online_word(session, _current_child(session).id, normalized, user.id)
        if online is not None:
            _prefetch_word_audio(online.result)
            return {**online.result.model_dump(), 'cache_hit': online.cache_hit, 'entry_id': online.entry_id}
    config = get_ai_config(session)
    if config is None or not config.enabled or not config.api_key_encrypted:
        code = 'DICTIONARY_LOCAL_MISS' if local_eligible else 'DICTIONARY_AI_REQUIRED'
        message = '本地和在线词典都没有找到这个词；配置 AI 后可继续查询。' if local_eligible else '短语和句子查询需要先配置辞典 AI。'
        raise HTTPException(409, detail={'code': code, 'message': message})
    client = OpenAiChatClient(ai_api_key(config), config.base_url, config.model, config.timeout_seconds)
    client.fingerprint = f'{config.protocol}:{config.base_url}:{config.model}:{config.temperature}'
    try:
        found = lookup_dictionary(session, _current_child(session).id, payload.text, payload.source_language, client, prompt_version='v2', owner_user_id=user.id)
    except OpenAiChatError as error:
        raise HTTPException(502, detail={'code': str(error), 'message': 'Dictionary AI request failed'}) from error
    except DictionaryServiceError as error:
        raise HTTPException(422, detail={'code': str(error), 'message': 'Dictionary result is invalid'}) from error
    _prefetch_word_audio(found.result)
    return {**found.result.model_dump(), 'cache_hit': found.cache_hit, 'entry_id': found.entry_id}


def _prefetch_word_audio(result) -> None:
    if getattr(result, 'item_type', None) == 'word':
        _start_audio_prefetch(result.source_text, result.source_language)


@router.post('/dictionary/entries/{entry_id}/audio')
def dictionary_audio(entry_id: str, payload: DictionaryAudioRequest, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    entry = session.get(DictionaryEntry, entry_id)
    if entry is None:
        raise HTTPException(404, detail={'code': 'DICTIONARY_ENTRY_NOT_FOUND', 'message': 'Dictionary entry not found'})
    history = session.scalar(select(DictionaryHistory).where(DictionaryHistory.entry_id == entry.id, DictionaryHistory.owner_user_id == user.id))
    require_resource_owner(session, history.owner_user_id if history else None, user)
    result = json.loads(entry.result_json)
    source_language = result.get('source_language', 'en')
    configured = get_tts_config(session)
    source = payload.source
    force_tts = source in ('configured', 'custom')
    selected_voice_id: str | None = None
    if source == 'custom':
        selected_voice_id = payload.voice_version_id or (configured.voice_version_id if configured and configured.pronunciation_source == 'custom' else None)
        if selected_voice_id is None:
            raise HTTPException(422, detail={'code': 'VOICE_VERSION_REQUIRED', 'message': '请先选择已就绪的克隆声音。'})
    elif source == 'default':
        selected_voice_id = payload.voice_version_id or (configured.voice_version_id if configured and configured.pronunciation_source == 'custom' else None)
    voice = session.get(VoiceVersion, selected_voice_id) if selected_voice_id else None
    if selected_voice_id and (voice is None or voice.status != 'ready'):
        raise HTTPException(409, detail={'code': 'VOICE_VERSION_NOT_READY', 'message': 'Selected voice is not ready'})
    if voice is not None:
        speaker = session.get(SpeakerProfile, voice.speaker_profile_id)
        if speaker is None:
            raise HTTPException(404, detail={'code': 'SPEAKER_NOT_FOUND', 'message': 'Speaker not found'})
        require_resource_owner(session, speaker.owner_user_id, user)
    is_word = result.get('item_type') == 'word'
    if voice is None and not force_tts and is_word:
        # Single words get real dictionary audio (free sources, cached); fall back to TTS on failure.
        dictionary_asset = ensure_word_audio_asset(
            session, result['source_text'], source_language,
            accent=payload.accent, owner_user_id=user.id, regenerate=payload.regenerate,
            timeout=INTERACTIVE_FETCH_TIMEOUT,
        )
        if dictionary_asset is not None:
            return {'asset_id': dictionary_asset.id, 'source': 'dictionary_audio'}
    if source == 'native':
        detail = {'code': 'DICTIONARY_NATIVE_UNAVAILABLE', 'message': '该条目没有辞典原生发音，请改用 AI 生成或克隆声音。'}
        raise HTTPException(422, detail=detail)
    text = result['source_text'] if source_language == 'en' else result['primary_translation']
    voice_key = voice.id if voice else 'default'
    cache_material = f'dictionary:v{AUDIO_VERSION}:{user.id}:{voice_key}:{text}'
    if payload.regenerate:
        cache_material += f':regenerated:{uuid4()}'
    cache_key = sha256(cache_material.encode()).hexdigest()
    asset = None if payload.regenerate else session.query(TtsAsset).filter_by(cache_key=cache_key, status='ready', owner_user_id=user.id).first()
    if asset is None:
        try:
            path = generate_text_with_voice(session, voice.id, text) if voice else generate_configured_tts(session, text)
        except ValueError as error:
            raise HTTPException(409, detail={'code': str(error), 'message': 'English TTS is not configured'}) from error
        asset = TtsAsset(owner_user_id=user.id, cache_key=cache_key, provider='mimo_voiceclone' if voice else 'configured_tts', model=voice.model if voice else 'configured', voice=voice_key, locale='en-US', speed=1.0, normalized_text=text[:160], path=str(path))
        session.add(asset)
        session.commit()
        session.refresh(asset)
    return {'asset_id': asset.id, 'source': 'voice_clone' if voice else 'configured_tts'}


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if cursor is None:
        return None
    try:
        created_at, history_id = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return datetime.fromisoformat(created_at), history_id
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(422, detail={'code': 'DICTIONARY_CURSOR_INVALID', 'message': 'Invalid cursor'})


def _encode_cursor(row) -> str:
    return base64.urlsafe_b64encode(json.dumps([row.created_at.isoformat(), row.id]).encode()).decode()


@router.get('/dictionary/history')
def history(session: DbSession, _user: Annotated[User, Depends(require_user)], limit: int = Query(default=50, ge=1, le=50), cursor: str | None = None) -> dict:
    rows = dictionary_history(session, _current_child(session).id, limit + 1, _decode_cursor(cursor))
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {'items': [{'id': row.id, **json.loads(row.entry.result_json)} for row in rows], 'next_cursor': _encode_cursor(rows[-1]) if has_more else None}


@router.delete('/dictionary/history/{history_id}', status_code=204)
def delete_history(history_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> None:
    try:
        delete_dictionary_history(session, _current_child(session).id, history_id)
    except DictionaryServiceError as error:
        raise HTTPException(404, detail={'code': str(error), 'message': 'Dictionary history not found'}) from error
