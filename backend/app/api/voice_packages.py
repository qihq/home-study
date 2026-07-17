from typing import Annotated, Literal
from uuid import uuid4
from pathlib import Path
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, require_resource_owner, require_user
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.models.user import User
from app.services.speakers import create_speaker, create_voice_version
from app.services.voice_packages import VoicePackageError, create_voice_package, pop_staged_voice_package, stage_voice_package_import
from app.core.config import get_settings

router = APIRouter(tags=['voice-packages'])


class ImportCommit(BaseModel):
    import_id: str
    strategy: Literal['merge', 'replace_profile_metadata', 'create_new']


class VoicePackageExport(BaseModel):
    password: str
    voice_version_ids: list[str]


@router.post('/speaker-profiles/{speaker_id}/export')
def export_voice_package(speaker_id: str, payload: VoicePackageExport, session: DbSession, user: Annotated[User, Depends(require_user)]) -> Response:
    speaker = session.get(SpeakerProfile, speaker_id)
    if speaker is None:
        raise HTTPException(404, detail={'code': 'SPEAKER_NOT_FOUND', 'message': '使用人不存在'})
    require_resource_owner(session, speaker.owner_user_id, user)
    voices = list(session.scalars(select(VoiceVersion).where(
        VoiceVersion.speaker_profile_id == speaker.id,
        VoiceVersion.id.in_(payload.voice_version_ids),
        VoiceVersion.status == 'ready',
    )))
    if len(voices) != len(set(payload.voice_version_ids)):
        raise HTTPException(422, detail={'code': 'VOICE_VERSION_NOT_READY', 'message': '所选声音未就绪'})
    audio_files: dict[str, bytes] = {}
    manifest_versions: list[dict] = []
    for voice in voices:
        if not voice.reference_audio_path or not Path(voice.reference_audio_path).is_file() or not voice.reference_sha256:
            raise HTTPException(422, detail={'code': 'VOICE_SAMPLE_UNSUPPORTED', 'message': '参考声音不可用'})
        audio_files[f'audio/{voice.id}.wav'] = Path(voice.reference_audio_path).read_bytes()
        manifest_versions.append({'id': voice.id, 'display_name': voice.display_name, 'provider': voice.provider, 'model': voice.model, 'reference_sha256': voice.reference_sha256})
    package = create_voice_package({'format_version': 1, 'speaker_profile_id': speaker.id, 'display_name': speaker.display_name, 'note': speaker.note, 'voice_versions': manifest_versions}, audio_files, payload.password)
    filename = f'{speaker.display_name}-voices.flvoice'.encode('ascii', 'ignore').decode() or 'voices.flvoice'
    return Response(package, media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.post('/speaker-profiles/import/inspect')
def inspect_import(
    _user: Annotated[User, Depends(require_user)],
    file: UploadFile = File(...),
    password: str = Form(...),
) -> dict:
    if file.size is not None and file.size > 50 * 1024 * 1024:
        raise HTTPException(413, detail={'code': 'VOICE_PACKAGE_INVALID', 'message': '声音包过大'})
    try:
        import_id, preview = stage_voice_package_import(file.file, password)
    except VoicePackageError as error:
        raise HTTPException(422, detail={'code': str(error), 'message': '声音包无效'}) from error
    return {
        'import_id': import_id,
        'speaker_profile_id': preview.manifest.get('speaker_profile_id'),
        'display_name': preview.manifest.get('display_name'),
        'voice_version_count': len(preview.manifest.get('voice_versions', [])),
    }


@router.post('/speaker-profiles/import/commit', status_code=status.HTTP_201_CREATED)
def commit_import(payload: ImportCommit, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        staged = pop_staged_voice_package(payload.import_id)
    except VoicePackageError as error:
        raise HTTPException(422, detail={'code': str(error), 'message': '导入预览已过期'}) from error
    preview = staged.preview
    source_id = preview.manifest.get('speaker_profile_id')
    existing = session.get(SpeakerProfile, source_id) if source_id else None
    if payload.strategy == 'create_new':
        speaker = create_speaker(
            session, f"{preview.manifest.get('display_name', '使用人')}（导入）", preview.manifest.get('note'),
        )
    elif existing is None:
        speaker = SpeakerProfile(
            id=source_id, display_name=preview.manifest.get('display_name', '使用人'), note=preview.manifest.get('note'),
        )
        session.add(speaker)
        session.commit()
        session.refresh(speaker)
    elif payload.strategy == 'replace_profile_metadata':
        existing.display_name = preview.manifest.get('display_name', existing.display_name)
        existing.note = preview.manifest.get('note')
        session.commit()
        session.refresh(existing)
        speaker = existing
    else:
        speaker = existing
    imported_voice_count = 0
    try:
        for metadata in preview.manifest.get('voice_versions', []):
            source_name = f"audio/{metadata['id']}.wav"
            with zipfile.ZipFile(staged.plaintext_path) as archive:
                audio = archive.read(source_name)
            path = get_settings().data_dir / 'voice-imports' / f'{uuid4().hex}.wav'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
            create_voice_version(
                session, speaker.id, metadata.get('display_name', '导入声音'),
                provider=metadata.get('provider', 'mimo'),
                model=metadata.get('model', 'mimo-v2.5-tts-voiceclone'),
                reference_audio_path=str(path), reference_mime_type='audio/wav',
                reference_sha256=metadata['reference_sha256'], status='ready',
            )
            imported_voice_count += 1
    finally:
        staged.plaintext_path.unlink(missing_ok=True)
    return {'id': speaker.id, 'display_name': speaker.display_name, 'voice_version_count': imported_voice_count}
