import base64
import json
from datetime import datetime
from hashlib import sha256
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_resource_owner, require_user
from app.models.child import Child
from app.models.dictionary import DictionaryEntry, DictionaryHistory
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.models.tts_asset import TtsAsset
from app.models.user import User
from app.services.ai_config import ai_api_key, get_ai_config
from app.services.dictionary import DictionaryServiceError, delete_dictionary_history, dictionary_history, lookup_dictionary
from app.services.openai_chat import OpenAiChatClient, OpenAiChatError
from app.workers.tts import generate_configured_tts
from app.workers.voice import generate_text_with_voice
from app.services.tts_config import get_tts_config
from app.services.tts import AUDIO_VERSION

router = APIRouter(tags=['dictionary'])


class DictionaryLookupRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    source_language: Literal['auto', 'en', 'zh'] = 'auto'


class DictionaryAudioRequest(BaseModel):
    voice_version_id: str | None = None


def _current_child(session: DbSession) -> Child:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        child = Child(display_name='Child', slug='default-child')
        session.add(child)
        session.flush()
    return child


@router.post('/dictionary/lookup')
def lookup(payload: DictionaryLookupRequest, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    config = get_ai_config(session)
    if config is None or not config.enabled or not config.api_key_encrypted:
        raise HTTPException(409, detail={'code': 'AI_NOT_CONFIGURED', 'message': 'Dictionary AI is not configured'})
    client = OpenAiChatClient(ai_api_key(config), config.base_url, config.model, config.timeout_seconds)
    client.fingerprint = f'{config.protocol}:{config.base_url}:{config.model}:{config.temperature}'
    try:
        found = lookup_dictionary(session, _current_child(session).id, payload.text, payload.source_language, client, prompt_version='v1', owner_user_id=user.id)
    except OpenAiChatError as error:
        raise HTTPException(502, detail={'code': str(error), 'message': 'Dictionary AI request failed'}) from error
    except DictionaryServiceError as error:
        raise HTTPException(422, detail={'code': str(error), 'message': 'Dictionary result is invalid'}) from error
    return {**found.result.model_dump(), 'cache_hit': found.cache_hit, 'entry_id': found.entry_id}


@router.post('/dictionary/entries/{entry_id}/audio')
def dictionary_audio(entry_id: str, payload: DictionaryAudioRequest, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    entry = session.get(DictionaryEntry, entry_id)
    if entry is None:
        raise HTTPException(404, detail={'code': 'DICTIONARY_ENTRY_NOT_FOUND', 'message': 'Dictionary entry not found'})
    history = session.scalar(select(DictionaryHistory).where(DictionaryHistory.entry_id == entry.id, DictionaryHistory.owner_user_id == user.id))
    require_resource_owner(session, history.owner_user_id if history else None, user)
    result = json.loads(entry.result_json)
    text = result['source_text'] if result.get('source_language') == 'en' else result['primary_translation']
    configured = get_tts_config(session)
    selected_voice_id = payload.voice_version_id or (configured.voice_version_id if configured and configured.pronunciation_source == 'custom' else None)
    voice = session.get(VoiceVersion, selected_voice_id) if selected_voice_id else None
    if selected_voice_id and (voice is None or voice.status != 'ready'):
        raise HTTPException(409, detail={'code': 'VOICE_VERSION_NOT_READY', 'message': 'Selected voice is not ready'})
    if voice is not None:
        speaker = session.get(SpeakerProfile, voice.speaker_profile_id)
        if speaker is None:
            raise HTTPException(404, detail={'code': 'SPEAKER_NOT_FOUND', 'message': 'Speaker not found'})
        require_resource_owner(session, speaker.owner_user_id, user)
    voice_key = voice.id if voice else 'default'
    cache_key = sha256(f'dictionary:v{AUDIO_VERSION}:{user.id}:{voice_key}:{text}'.encode()).hexdigest()
    asset = session.query(TtsAsset).filter_by(cache_key=cache_key, status='ready', owner_user_id=user.id).first()
    if asset is None:
        try:
            path = generate_text_with_voice(session, voice.id, text) if voice else generate_configured_tts(session, text)
        except ValueError as error:
            raise HTTPException(409, detail={'code': str(error), 'message': 'English TTS is not configured'}) from error
        asset = TtsAsset(owner_user_id=user.id, cache_key=cache_key, provider='mimo_voiceclone' if voice else 'configured_tts', model=voice.model if voice else 'configured', voice=voice_key, locale='en-US', speed=1.0, normalized_text=text[:160], path=str(path))
        session.add(asset)
        session.commit()
        session.refresh(asset)
    return {'asset_id': asset.id}


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
