import socket
import time
import json
import traceback
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.services.jobs import claim_next_job
from app.workers.video import process_assemble_video, process_transcode_video
from app.workers.tts import process_generate_tts
from app.workers.voice import process_normalize_voice_sample, process_voice_preview


def repair_pending_work(session: Session) -> None:
    from sqlalchemy import select
    from app.models.recording import Recording
    from app.models.speaker import VoiceVersion
    from app.models.job import Job
    from app.services.jobs import enqueue_once
    from app.services.learning_items import enqueue_missing_tts_for_confirmed_items

    for recording in session.scalars(select(Recording).where(Recording.status == 'transcode_failed', Recording.source_path.is_not(None))):
        recording.status = 'transcoding'
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


def _set_progress(session: Session, job_id: str, progress: int) -> None:
    from app.models.job import Job
    job = session.get(Job, job_id)
    if job is not None and job.status == 'running':
        job.progress = progress
        session.commit()


def run_once(session: Session, worker_id: str, now: datetime | None = None) -> bool:
    job = claim_next_job(session, worker_id, now or datetime.now(timezone.utc))
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
    }
    handler = handlers.get(job.type)
    if handler is None:
        job.status = 'failed'
        job.error_code = 'UNKNOWN_JOB_TYPE'
        job.error_detail = f'No handler for {job.type}'
    else:
        try:
            handler(session, job.entity_id, lambda progress: _set_progress(session, job.id, progress))
            if job.status == 'running':
                job.status = 'succeeded'
                job.progress = 100
        except Exception as error:
            session.rollback()
            job = session.get(type(job), job.id)
            job.status = 'failed'
            job.error_code = 'JOB_PROCESSING_FAILED'
            job.error_detail = str(error)[:500] or '任务处理失败，请在管理页重试。'
    session.commit()
    return True


def main() -> None:
    worker_id = f'{socket.gethostname()}-{id(object())}'
    with get_session_factory()() as session:
        repair_pending_work(session)
    while True:
        try:
            from app.core.config import get_settings
            heartbeat = get_settings().data_dir / 'worker-heartbeat.json'
            heartbeat.write_text(json.dumps({'worker_id': worker_id, 'updated_at': datetime.now(timezone.utc).isoformat()}), encoding='utf-8')
            with get_session_factory()() as session:
                processed = run_once(session, worker_id)
            if not processed:
                time.sleep(2)
        except Exception:
            traceback.print_exc()
            time.sleep(2)


if __name__ == '__main__':
    main()
