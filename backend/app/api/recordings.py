from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.api.deps import DbSession, require_user
from app.models.recording import Recording
from app.models.user import User
from app.services.recordings import ChunkConflict, create_recording, delete_recording, missing_sequences, upload_chunk
from app.services.jobs import enqueue_once, reset_failed_job

router = APIRouter(tags=['recordings'])
class CreateRecording(BaseModel): language_type: Literal['chinese','english']
class CompleteRecording(BaseModel): final_chunk_count: int = Field(ge=0, le=10000)
class UpdateRecording(BaseModel): title: str | None = Field(default=None, max_length=160)

def get_recording(session: DbSession, recording_id: str) -> Recording:
    record = session.scalar(select(Recording).where(Recording.id == recording_id))
    if not record: raise HTTPException(404, detail={'code':'RECORDING_NOT_FOUND','message':'录制不存在'})
    return record

@router.post('/recordings', status_code=status.HTTP_201_CREATED)
def create(payload: CreateRecording, session: DbSession, _user: Annotated[User, Depends(require_user)]):
    record = create_recording(session, payload.language_type); return {'id':record.id,'status':record.status}


@router.get('/recordings')
def list_recordings(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> list[dict]:
    records = session.scalars(select(Recording).order_by(Recording.created_at.desc())).all()
    return [
        {
            'id': record.id, 'reading_date': record.reading_date.isoformat(), 'language_type': record.language_type,
            'title': record.title,
            'status': record.status, 'is_official': record.is_official,
            'duration_ms': record.verified_duration_ms, 'download_ready': record.status == 'ready' and bool(record.compressed_path),
        }
        for record in records
    ]

@router.put('/recordings/{recording_id}/chunks/{sequence}')
async def put_chunk(recording_id: str, sequence: int, request: Request, session: DbSession, x_chunk_sha256: Annotated[str, Header()], _user: Annotated[User, Depends(require_user)]):
    if sequence < 0: raise HTTPException(422, detail={'code':'INVALID_SEQUENCE','message':'片段序号无效'})
    try: idem = upload_chunk(session, get_recording(session, recording_id), sequence, await request.body(), x_chunk_sha256, request.headers.get('content-type','application/octet-stream'))
    except ValueError: raise HTTPException(422, detail={'code':'CHUNK_HASH_MISMATCH','message':'片段校验失败'})
    except ChunkConflict: raise HTTPException(409, detail={'code':'CHUNK_HASH_MISMATCH','message':'片段冲突'})
    return {'idempotent':idem}

@router.post('/recordings/{recording_id}/complete')
def complete(recording_id: str, payload: CompleteRecording, session: DbSession, _user: Annotated[User, Depends(require_user)]):
    record = get_recording(session, recording_id); missing = missing_sequences(session, record.id, payload.final_chunk_count)
    if not missing:
        record.status='assembling'
        enqueue_once(session, 'assemble_video', record.id)
        session.commit()
    return {'missing_sequences':missing,'status':record.status}


@router.post('/recordings/{recording_id}/retry', status_code=status.HTTP_202_ACCEPTED)
def retry(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = get_recording(session, recording_id)
    if record.status == 'transcode_failed' and record.source_path and record.source_validated_at:
        record.status = 'transcoding'
        job_type = 'transcode_video'
    elif record.status == 'assemble_failed':
        record.status = 'assembling'
        job_type = 'assemble_video'
    else:
        raise HTTPException(409, detail={'code': 'RECORDING_NOT_RETRYABLE', 'message': '当前视频状态不支持重新处理'})
    reset_failed_job(session, job_type, record.id)
    session.commit()
    return {'status': record.status}


@router.get('/recordings/{recording_id}/chunks')
def received_chunks(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = get_recording(session, recording_id)
    from app.models.recording import RecordingChunk
    sequences = session.scalars(select(RecordingChunk.sequence).where(RecordingChunk.recording_id == record.id).order_by(RecordingChunk.sequence)).all()
    return {'received_sequences': sequences, 'status': record.status}


@router.post('/recordings/{recording_id}/abandon')
def abandon(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = get_recording(session, recording_id)
    if record.status in {'created', 'recording', 'uploading'}:
        record.status = 'abandoned'
        session.commit()
    return {'status': record.status}


@router.delete('/recordings/{recording_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> None:
    delete_recording(session, get_recording(session, recording_id))


@router.patch('/recordings/{recording_id}')
def update(recording_id: str, payload: UpdateRecording, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = get_recording(session, recording_id)
    record.title = payload.title.strip() if payload.title else None
    session.commit()
    return {'id': record.id, 'title': record.title}


@router.post('/recordings/{recording_id}/make-official')
def make_official(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = get_recording(session, recording_id)
    if record.source_validated_at is None or record.source_missing_at is not None:
        raise HTTPException(409, detail={'code': 'SOURCE_VIDEO_NOT_READY', 'message': '源视频尚未验证完成'})
    related = session.scalars(select(Recording).where(
        Recording.child_id == record.child_id,
        Recording.reading_date == record.reading_date,
        Recording.language_type == record.language_type,
    )).all()
    for item in related:
        item.is_official = item.id == record.id
    session.commit()
    return {'id': record.id, 'is_official': True}


@router.get('/recordings/{recording_id}/download/720p')
def download_720p(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]):
    record = get_recording(session, recording_id)
    if record.status != 'ready' or not record.compressed_path:
        raise HTTPException(409, detail={'code':'COMPRESSED_VIDEO_NOT_READY','message':'压缩视频尚未完成'})
    path = __import__('pathlib').Path(record.compressed_path)
    if not path.is_file():
        raise HTTPException(404, detail={'code':'COMPRESSED_VIDEO_MISSING','message':'压缩视频文件缺失'})
    return FileResponse(path, media_type='video/mp4', filename=f'{record.reading_date}-{record.language_type}-720p.mp4')


@router.get('/recordings/{recording_id}/preview')
def preview(recording_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]):
    record = get_recording(session, recording_id)
    if record.status != 'ready' or not record.compressed_path:
        raise HTTPException(409, detail={'code': 'COMPRESSED_VIDEO_NOT_READY', 'message': 'Video is not ready'})
    path = __import__('pathlib').Path(record.compressed_path)
    if not path.is_file():
        raise HTTPException(404, detail={'code': 'COMPRESSED_VIDEO_MISSING', 'message': 'Video file is missing'})
    return FileResponse(path, media_type='video/mp4')
