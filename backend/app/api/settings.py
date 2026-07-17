from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_user
from app.core.config import get_settings
from app.models.user import User
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.api.deps import require_resource_owner
from app.models.job import Job
from app.services.backups import create_backup
from app.services.tts_config import api_key, get_tts_config, mask_key, save_tts_config
from app.services.learning_items import enqueue_missing_tts_for_confirmed_items
from app.services.ai_config import (
    ai_api_key, get_ai_config, get_spelling_ocr_config, present_ai_config,
    present_spelling_ocr_config, save_ai_config, save_spelling_ocr_config, spelling_ocr_provider,
)
from app.services.openai_chat import OpenAiChatClient, OpenAiChatError

router = APIRouter(tags=['settings'])


class TtsConfigPayload(BaseModel):
    protocol: str = Field(pattern='^(mimo|openai_compatible)$')
    base_url: AnyHttpUrl
    api_key: str | None = Field(default=None, max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    voice: str = Field(min_length=1, max_length=200)
    speed: float = Field(ge=0.5, le=2.0)
    pronunciation_source: str = Field(default='configured', pattern='^(configured|custom)$')
    voice_version_id: str | None = None


class AiConfigPayload(BaseModel):
    protocol: str = Field(pattern='^openai_chat_compatible$')
    display_name: str = Field(min_length=1, max_length=100)
    base_url: AnyHttpUrl
    api_key: str | None = Field(default=None, max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(default=0.1, ge=0, le=1)
    timeout_seconds: int = Field(default=45, ge=10, le=120)
    enabled: bool = True


class SpellingOcrConfigPayload(BaseModel):
    source: str = Field(pattern='^(dictionary|separate)$')
    protocol: str = Field(default='openai_chat_compatible', pattern='^openai_chat_compatible$')
    display_name: str = Field(default='Spelling OCR AI', min_length=1, max_length=100)
    base_url: AnyHttpUrl | None = None
    api_key: str | None = Field(default=None, max_length=1000)
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.0, ge=0, le=1)
    timeout_seconds: int = Field(default=45, ge=10, le=120)
    enabled: bool = True


def present_tts_config(config):
    if config is None:
        return {'protocol': 'mimo', 'base_url': 'https://api.xiaomimimo.com/v1', 'model': 'mimo-v2.5-tts', 'voice': 'Chloe', 'speed': 1.0, 'pronunciation_source': 'configured', 'voice_version_id': None, 'api_key_configured': False, 'api_key_mask': None}
    return {'protocol': config.protocol, 'base_url': config.base_url, 'model': config.model, 'voice': config.voice, 'speed': config.speed, 'pronunciation_source': config.pronunciation_source, 'voice_version_id': config.voice_version_id, 'api_key_configured': bool(config.api_key_encrypted), 'api_key_mask': mask_key(api_key(config))}


@router.get('/settings/tts')
def get_tts(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    config = get_tts_config(session)
    return present_tts_config(config)


@router.patch('/settings/tts')
def update_tts(payload: TtsConfigPayload, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    if payload.pronunciation_source == 'custom':
        voice = session.get(VoiceVersion, payload.voice_version_id) if payload.voice_version_id else None
        if voice is None or voice.status != 'ready':
            raise HTTPException(409, detail={'code': 'VOICE_VERSION_NOT_READY', 'message': 'Selected cloned voice is unavailable'})
        speaker = session.get(SpeakerProfile, voice.speaker_profile_id)
        require_resource_owner(session, speaker.owner_user_id if speaker else None, user)
    config = save_tts_config(session, protocol=payload.protocol, base_url=str(payload.base_url).rstrip('/'), api_key_value=payload.api_key, model=payload.model, voice=payload.voice, speed=payload.speed, pronunciation_source=payload.pronunciation_source, voice_version_id=payload.voice_version_id)
    return {**present_tts_config(config), 'queued_item_count': enqueue_missing_tts_for_confirmed_items(session)}


@router.get('/settings/ai')
def get_ai(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    return present_ai_config(get_ai_config(session))


@router.patch('/settings/ai')
def update_ai(payload: AiConfigPayload, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    config = save_ai_config(
        session,
        protocol=payload.protocol,
        display_name=payload.display_name,
        base_url=str(payload.base_url).rstrip('/'),
        api_key_value=payload.api_key,
        model=payload.model,
        temperature=payload.temperature,
        timeout_seconds=payload.timeout_seconds,
        enabled=payload.enabled,
    )
    return present_ai_config(config)


@router.post('/settings/ai/test')
def test_ai_connection(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    config = get_ai_config(session)
    if config is None or not config.enabled or not config.api_key_encrypted:
        raise HTTPException(409, detail={'code': 'AI_NOT_CONFIGURED', 'message': '电子辞典 AI 未配置'})
    started = monotonic()
    try:
        OpenAiChatClient(
            ai_api_key(config), config.base_url, config.model, config.timeout_seconds,
        ).complete([{'role': 'user', 'content': 'apple'}])
    except OpenAiChatError as error:
        messages = {
            'AI_AUTH_FAILED': 'AI 服务认证失败',
            'AI_TIMEOUT': 'AI 服务请求超时',
        }
        code = str(error)
        raise HTTPException(502, detail={'code': code, 'message': messages.get(code, 'AI 服务请求失败')}) from error
    return {
        'ok': True,
        'display_name': config.display_name,
        'model': config.model,
        'latency_ms': int((monotonic() - started) * 1000),
    }


@router.get('/settings/spelling-ocr')
def get_spelling_ocr(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    return present_spelling_ocr_config(get_spelling_ocr_config(session))


@router.patch('/settings/spelling-ocr')
def update_spelling_ocr(payload: SpellingOcrConfigPayload, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    if payload.source == 'separate' and (payload.base_url is None or not payload.model):
        raise HTTPException(422, detail={'code': 'OCR_AI_CONFIGURATION_INVALID', 'message': 'Separate OCR AI requires an endpoint and model'})
    config = save_spelling_ocr_config(
        session, source=payload.source, protocol=payload.protocol, display_name=payload.display_name,
        base_url=str(payload.base_url).rstrip('/') if payload.base_url else None, api_key_value=payload.api_key,
        model=payload.model, temperature=payload.temperature, timeout_seconds=payload.timeout_seconds, enabled=payload.enabled,
    )
    return present_spelling_ocr_config(config)


@router.post('/settings/spelling-ocr/test')
def test_spelling_ocr_connection(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        secret, base_url, model, timeout_seconds, _temperature = spelling_ocr_provider(session)
    except ValueError as error:
        raise HTTPException(409, detail={'code': str(error), 'message': 'Spelling recognition AI is not configured'}) from error
    started = monotonic()
    try:
        OpenAiChatClient(secret, base_url, model, timeout_seconds).complete([{'role': 'user', 'content': 'Reply with {"ok":true}.'}])
    except OpenAiChatError as error:
        raise HTTPException(502, detail={'code': str(error), 'message': 'Spelling recognition AI request failed'}) from error
    return {'ok': True, 'model': model, 'latency_ms': int((monotonic() - started) * 1000)}


@router.get('/settings/tts/status')
def tts_status(_user: Annotated[User, Depends(require_user)]) -> dict[str, bool | str]:
    settings = get_settings()
    configured = bool(settings.mimo_api_key and settings.mimo_api_base_url and settings.mimo_tts_model and settings.mimo_tts_voice)
    return {'configured': configured, 'provider': 'mimo'}


@router.post('/settings/backup', status_code=201)
def backup(_user: Annotated[User, Depends(require_user)]) -> dict[str, str]:
    created = create_backup()
    return {'filename': created.name}


@router.get('/settings/failed-tasks')
def failed_tasks(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> list[dict]:
    jobs = session.scalars(select(Job).where(
        Job.status == 'failed',
        Job.type.in_(['normalize_voice_sample', 'voice_preview']),
    ).order_by(Job.updated_at.desc())).all()
    return [{'id': job.id, 'type': job.type, 'entity_id': job.entity_id, 'error_code': job.error_code} for job in jobs]


@router.post('/settings/failed-tasks/{job_id}/retry')
def retry_failed_task(job_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    job = session.get(Job, job_id)
    if job is None or job.status != 'failed' or job.type not in {'normalize_voice_sample', 'voice_preview'}:
        raise HTTPException(404, detail={'code': 'FAILED_TASK_NOT_FOUND', 'message': 'Failed task not found'})
    job.status = 'queued'
    job.error_code = job.error_detail = None
    job.locked_by = job.locked_at = None
    session.commit()
    return {'id': job.id, 'status': job.status}
