import socket
import time
import json
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.services.dictionary_updates import enqueue_if_due, process_update_dictionary
from app.services.jobs import claim_next_job
from app.workers.video import process_assemble_video, process_transcode_video
from app.workers.tts import process_generate_tts
from app.workers.voice import process_normalize_voice_sample, process_voice_preview
from app.workers.activity import WorkerActivity, touch_worker_heartbeat
from app.workers.video import MediaError

# Errors that retrying cannot fix: the source file itself is unusable.
# Jobs failing with these stop immediately instead of burning retry cycles.
PERMANENT_MEDIA_ERRORS = {
    'NO_VIDEO_TRACK', 'NO_AUDIO_TRACK', 'SOURCE_INVALID', 'SOURCE_MISSING',
    'RECORDING_NOT_FOUND', 'MP4_BOX_TRUNCATED',
    'FMP4_INITIALIZATION_INVALID', 'FMP4_INITIALIZATION_MISSING', 'FMP4_CHUNK_LAYOUT_INVALID',
}


def repair_pending_work(session: Session) -> None:
    from sqlalchemy import select
    from app.models.recording import Recording
    from app.models.speaker import VoiceVersion
    from app.models.job import Job
    from app.services.jobs import enqueue_once
    from app.services.learning_items import enqueue_dictionary_audio_upgrade, enqueue_missing_tts_for_confirmed_items

    for recording in session.scalars(select(Recording).where(Recording.status == 'transcode_failed', Recording.source_path.is_not(None))):
        latest = session.scalar(select(Job).where(Job.type == 'transcode_video', Job.entity_id == recording.id).order_by(Job.created_at.desc()))
        if latest is not None and latest.error_code in PERMANENT_MEDIA_ERRORS:
            continue
        if latest is None or latest.attempts < latest.max_attempts:
            recording.status = 'transcoding'
            if latest is not None and latest.status == 'failed':
                latest.status = 'queued'
                latest.error_code = None
                latest.error_detail = None
            else:
                enqueue_once(session, 'transcode_video', recording.id)
    for recording in session.scalars(select(Recording).where(Recording.status == 'assembling')):
        enqueue_once(session, 'assemble_video', recording.id)
    for recording in session.scalars(select(Recording).where(Recording.status == 'transcoding', Recording.source_path.is_not(None))):
        enqueue_once(session, 'transcode_video', recording.id)
    for voice in session.scalars(select(VoiceVersion).where(
        VoiceVersion.status == 'failed',
        VoiceVersion.failure_code == 'VOICE_SAMPLE_UNSUPPORTED',
        VoiceVersion.reference_audio_path.is_not(None),
    )):
        voice.status = 'processing'
        voice.failure_code = None
        enqueue_once(session, 'normalize_voice_sample', voice.id)
    failed_tts = list(session.scalars(select(Job).where(
        Job.type == 'generate_tts', Job.status == 'failed', Job.attempts < Job.max_attempts,
    ).order_by(Job.entity_id, Job.created_at.desc())))
    latest_by_entity = {}
    for job in failed_tts:
        if job.entity_id in latest_by_entity:
            job.status = 'superseded'
            continue
        latest_by_entity[job.entity_id] = job
        job.status = 'queued'
        job.progress = 0
        job.error_code = None
        job.error_detail = None
        job.locked_by = None
        job.locked_at = None
    session.commit()
    enqueue_missing_tts_for_confirmed_items(session)
    enqueue_dictionary_audio_upgrade(session)
    from app.services.tts_maintenance import maybe_cleanup_stale_tts_assets
    maybe_cleanup_stale_tts_assets(session)
    enqueue_if_due(session)


def _set_progress(session: Session, job_id: str, progress: int) -> None:
    from app.models.job import Job
    job = session.get(Job, job_id)
    if job is not None and job.status == 'running':
        job.progress = progress
        session.commit()


def _retry_media_job(session: Session, job, current_time: datetime, error_code: str, error_detail: str) -> None:
    from app.models.recording import Recording

    if job.attempts < job.max_attempts:
        job.status = 'queued'
        job.run_after = current_time + timedelta(minutes=min(2 ** job.attempts, 60))
        recording = session.get(Recording, job.entity_id)
        if recording is not None:
            recording.status = 'assembling' if job.type == 'assemble_video' else 'transcoding'
    else:
        job.status = 'failed'
    job.error_code = error_code[:80]
    job.error_detail = error_detail[:500]
    job.locked_by = None
    job.locked_at = None


def run_once(session: Session, worker_id: str, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(timezone.utc)
    job = claim_next_job(session, worker_id, current_time)
    if job is None:
        return False
    job.progress = 5
    session.commit()
    handlers = {
        'assemble_video': process_assemble_video,
        'transcode_video': process_transcode_video,
        'generate_tts': process_generate_tts,
        'normalize_voice_sample': process_normalize_voice_sample,
        'voice_preview': process_voice_preview,
        'update_dictionary': process_update_dictionary,
    }
    handler = handlers.get(job.type)
    if handler is None:
        job.status = 'failed'
        job.error_code = 'UNKNOWN_JOB_TYPE'
        job.error_detail = f'No handler for {job.type}'
    else:
        from app.core.config import get_settings
        activity = WorkerActivity(get_settings().data_dir, worker_id, job.id)
        try:
            activity.start()
            handler(session, job.entity_id, lambda progress: _set_progress(session, job.id, progress))
            session.refresh(job)
            if job.type in {'assemble_video', 'transcode_video'}:
                from app.models.recording import Recording
                recording = session.get(Recording, job.entity_id)
                failed_state = 'assemble_failed' if job.type == 'assemble_video' else 'transcode_failed'
                if recording is not None and recording.status == failed_state:
                    raise MediaError(failed_state.upper())
            if job.status == 'running':
                job.status = 'succeeded'
                job.progress = 100
        except MediaError as error:
            session.rollback()
            job = session.get(type(job), job.id)
            code = str(error) or 'MEDIA_PROCESSING_FAILED'
            if code in PERMANENT_MEDIA_ERRORS:
                job.status = 'failed'
                job.error_code = code[:80]
                job.error_detail = str(error)[:500]
                job.locked_by = None
                job.locked_at = None
            else:
                _retry_media_job(session, job, current_time, code, str(error))
        except Exception as error:
            session.rollback()
            job = session.get(type(job), job.id)
            detail = str(error) or '任务处理失败，请在管理页重试。'
            if job.type in {'assemble_video', 'transcode_video'}:
                _retry_media_job(session, job, current_time, 'JOB_PROCESSING_FAILED', detail)
            else:
                job.status = 'failed'
                job.error_code = 'JOB_PROCESSING_FAILED'
                job.error_detail = detail[:500]
        finally:
            activity.stop()
    session.commit()
    return True


def main() -> None:
    worker_id = f'{socket.gethostname()}-{id(object())}'
    with get_session_factory()() as session:
        repair_pending_work(session)
    while True:
        try:
            from app.core.config import get_settings
            touch_worker_heartbeat(get_settings().data_dir, worker_id, busy=False)
            with get_session_factory()() as session:
                processed = run_once(session, worker_id)
            if not processed:
                with get_session_factory()() as session:
                    repair_pending_work(session)
                time.sleep(2)
        except Exception:
            traceback.print_exc()
            time.sleep(2)


if __name__ == '__main__':
    main()
