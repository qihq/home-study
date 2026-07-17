from typing import Annotated
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_resource_owner, require_user
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.models.user import User
from app.services.speakers import create_speaker, create_voice_version, delete_voice_version, make_default
from app.models.job import Job
from app.services.jobs import enqueue_once
from app.core.config import get_settings

router = APIRouter(tags=['speakers'])


class SpeakerInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    note: str | None = None
    avatar_color: str = 'blue'


class VoiceInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    style_instruction: str | None = None


class RenameInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


@router.get('/speaker-profiles')
def list_speakers(session: DbSession, user: Annotated[User, Depends(require_user)]) -> list[dict]:
    speakers = [
        {'id': speaker.id, 'display_name': speaker.display_name, 'active': speaker.active,
         'default_voice_version_id': speaker.default_voice_version_id}
        for speaker in session.scalars(select(SpeakerProfile).where(SpeakerProfile.active.is_(True)))
        if _can_access_speaker(session, speaker, user)
    ]
    if not speakers:
        speaker = create_speaker(session, '我的声音', owner_user_id=user.id)
        speakers.append({'id': speaker.id, 'display_name': speaker.display_name, 'active': speaker.active, 'default_voice_version_id': None})
    return speakers


@router.get('/voice-versions')
def list_voice_versions(
    session: DbSession,
    user: Annotated[User, Depends(require_user)],
    ready: bool = False,
    include_selection_metadata: bool = False,
    include_management_metadata: bool = False,
) -> list[dict]:
    statement = select(VoiceVersion, SpeakerProfile.display_name).join(SpeakerProfile)
    if ready:
        statement = statement.where(VoiceVersion.status == 'ready')
    voices = []
    for voice, speaker_name in session.execute(statement.order_by(SpeakerProfile.display_name, VoiceVersion.created_at)):
        if not _can_access_speaker(session, session.get(SpeakerProfile, voice.speaker_profile_id), user):
            continue
        jobs = session.scalars(select(Job).where(Job.entity_id == voice.id, Job.type.in_(['normalize_voice_sample', 'voice_preview']))).all()
        normalize = next((job for job in jobs if job.type == 'normalize_voice_sample'), None)
        preview = next((job for job in jobs if job.type == 'voice_preview'), None)
        if voice.status == 'ready':
            voice_progress = 100
        elif preview is not None:
            voice_progress = 50 + round(preview.progress / 2)
        elif normalize is not None:
            voice_progress = round(normalize.progress / 2)
        else:
            voice_progress = 0
        item = {'id': voice.id, 'display_name': f'{speaker_name} / {voice.display_name}'}
        if include_selection_metadata:
            item.update({'speaker_profile_id': voice.speaker_profile_id, 'status': voice.status})
        if include_management_metadata or not ready:
            item.update({
                'speaker_profile_id': voice.speaker_profile_id, 'status': voice.status,
                'failure_code': voice.failure_code,
                'progress': voice_progress,
            })
        voices.append(item)
    return voices


@router.post('/speaker-profiles', status_code=status.HTTP_201_CREATED)
def create(payload: SpeakerInput, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    speaker = create_speaker(session, payload.display_name, payload.note, payload.avatar_color, user.id)
    return {'id': speaker.id, 'display_name': speaker.display_name}


@router.post('/speaker-profiles/{speaker_id}/voice-versions', status_code=status.HTTP_201_CREATED)
def create_voice(speaker_id: str, payload: VoiceInput, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        _require_speaker_owner(session, speaker_id, user)
        voice = create_voice_version(
            session, speaker_id, payload.display_name,
            style_instruction=payload.style_instruction or '标准美式英语，清晰、自然，适合儿童默写，速度稍慢',
        )
    except ValueError as error:
        raise HTTPException(404, detail={'code': str(error), 'message': '使用人不存在'}) from error
    return {'id': voice.id, 'status': voice.status}


@router.post('/speaker-profiles/{speaker_id}/voice-versions/upload', status_code=status.HTTP_201_CREATED)
def upload_voice(
    speaker_id: str,
    session: DbSession,
    user: Annotated[User, Depends(require_user)],
    file: UploadFile = File(...),
    consent_confirmed: bool = Form(...),
) -> dict:
    _require_speaker_owner(session, speaker_id, user)
    if not consent_confirmed:
        raise HTTPException(422, detail={'code': 'VOICE_CONSENT_REQUIRED', 'message': '需要确认声音授权'})
    suffix = Path(file.filename or '').suffix.lower() or '.bin'
    destination = get_settings().uploads_dir / 'voice' / f'{uuid4().hex}{suffix}'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(file.file.read())
    try:
        voice = create_voice_version(
            session, speaker_id, '待处理声音', reference_audio_path=str(destination), status='processing',
        )
    except ValueError as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(404, detail={'code': str(error), 'message': '使用人不存在'}) from error
    enqueue_once(session, 'normalize_voice_sample', voice.id)
    session.commit()
    return {'id': voice.id, 'status': voice.status}


@router.post('/voice-versions/{voice_id}/make-default')
def default_voice(voice_id: str, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    voice = session.get(VoiceVersion, voice_id)
    if voice is not None:
        _require_speaker_owner(session, voice.speaker_profile_id, user)
    if voice is None:
        raise HTTPException(404, detail={'code': 'VOICE_VERSION_NOT_FOUND', 'message': '声音版本不存在'})
    try:
        speaker = make_default(session, voice.speaker_profile_id, voice.id)
    except ValueError as error:
        raise HTTPException(409, detail={'code': str(error), 'message': '声音版本尚未就绪'}) from error
    return {'speaker_profile_id': speaker.id, 'default_voice_version_id': speaker.default_voice_version_id}


@router.patch('/voice-versions/{voice_id}')
def rename_voice(voice_id: str, payload: RenameInput, session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict:
    voice = session.get(VoiceVersion, voice_id)
    if voice is None:
        raise HTTPException(404, detail={'code': 'VOICE_VERSION_NOT_FOUND', 'message': 'Voice version not found'})
    _require_speaker_owner(session, voice.speaker_profile_id, user)
    voice.display_name = payload.display_name.strip()
    session.commit()
    return {'id': voice.id, 'display_name': voice.display_name}


@router.delete('/voice-versions/{voice_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_voice(voice_id: str, session: DbSession, user: Annotated[User, Depends(require_user)]) -> None:
    voice = session.get(VoiceVersion, voice_id)
    if voice is None:
        raise HTTPException(404, detail={'code': 'VOICE_VERSION_NOT_FOUND', 'message': 'Voice version not found'})
    _require_speaker_owner(session, voice.speaker_profile_id, user)
    if voice.reference_audio_path:
        Path(voice.reference_audio_path).unlink(missing_ok=True)
    get_settings().tts_dir.joinpath('voice-previews', f'{voice.id}.wav').unlink(missing_ok=True)
    delete_voice_version(session, voice.id)


@router.delete('/speaker-profiles/{speaker_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_speaker(speaker_id: str, session: DbSession, user: Annotated[User, Depends(require_user)]) -> None:
    speaker = _require_speaker_owner(session, speaker_id, user)
    voices = session.scalars(select(VoiceVersion).where(VoiceVersion.speaker_profile_id == speaker.id)).all()
    for voice in voices:
        if voice.reference_audio_path:
            Path(voice.reference_audio_path).unlink(missing_ok=True)
        get_settings().tts_dir.joinpath('voice-previews', f'{voice.id}.wav').unlink(missing_ok=True)
    session.delete(speaker)
    session.commit()


@router.get('/voice-versions/{voice_id}/preview')
def preview_voice(voice_id: str, session: DbSession, user: Annotated[User, Depends(require_user)]):
    voice = session.get(VoiceVersion, voice_id)
    if voice is None or voice.status != 'ready':
        raise HTTPException(409, detail={'code': 'VOICE_VERSION_NOT_READY', 'message': '声音版本尚未就绪'})
    _require_speaker_owner(session, voice.speaker_profile_id, user)
    path = get_settings().tts_dir / 'voice-previews' / f'{voice.id}.wav'
    if not path.is_file():
        raise HTTPException(404, detail={'code': 'VOICE_PREVIEW_MISSING', 'message': '声音试听文件不存在'})
    return FileResponse(path, media_type='audio/wav')


def _can_access_speaker(session, speaker: SpeakerProfile | None, user: User) -> bool:
    if speaker is None:
        return False
    try:
        require_resource_owner(session, speaker.owner_user_id, user)
    except HTTPException:
        return False
    return True


def _require_speaker_owner(session, speaker_id: str, user: User) -> SpeakerProfile:
    speaker = session.get(SpeakerProfile, speaker_id)
    if speaker is None:
        raise HTTPException(404, detail={'code': 'SPEAKER_NOT_FOUND', 'message': 'speaker not found'})
    require_resource_owner(session, speaker.owner_user_id, user)
    return speaker
