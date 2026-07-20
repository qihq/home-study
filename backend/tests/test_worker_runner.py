from datetime import datetime, timezone


def test_run_once_claims_and_marks_unknown_job_failed(session) -> None:
    from app.models.job import Job
    from app.workers.runner import run_once

    job = Job(type='unknown_job', entity_id='x')
    session.add(job)
    session.commit()

    processed = run_once(session, 'test-worker', now=datetime.now(timezone.utc))
    session.refresh(job)

    assert processed is True
    assert job.status == 'failed'
    assert job.error_code == 'UNKNOWN_JOB_TYPE'


def test_run_once_marks_handler_exception_failed_without_crashing(session, monkeypatch) -> None:
    from app.models.job import Job
    from app.workers.runner import run_once

    job = Job(type='generate_tts', entity_id='word-1')
    session.add(job); session.commit()
    monkeypatch.setattr('app.workers.runner.process_generate_tts', lambda *_: (_ for _ in ()).throw(RuntimeError('network down')))

    assert run_once(session, 'test-worker') is True
    session.refresh(job)
    assert job.status == 'failed'
    assert job.error_code == 'JOB_PROCESSING_FAILED'


def test_run_once_retries_media_failure_and_keeps_recording_processing(session, monkeypatch) -> None:
    from datetime import date
    from app.models.child import Child
    from app.models.job import Job
    from app.models.recording import Recording
    from app.workers.runner import run_once
    from app.workers.video import MediaError

    child = Child(display_name='孩子', slug='retry-media-child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=date.today(), language_type='english', status='transcoding', source_path='/data/source.mp4')
    session.add(recording); session.flush()
    job = Job(type='transcode_video', entity_id=recording.id, max_attempts=3)
    session.add(job); session.commit()
    monkeypatch.setattr('app.workers.runner.process_transcode_video', lambda *_: (_ for _ in ()).throw(MediaError('ENCODER_BUSY')))

    assert run_once(session, 'test-worker') is True
    session.refresh(job); session.refresh(recording)

    assert job.status == 'queued'
    assert job.error_code == 'ENCODER_BUSY'
    assert job.run_after > datetime.now(timezone.utc).replace(tzinfo=None)
    assert recording.status == 'transcoding'


def test_worker_startup_requeues_media_voice_and_stale_tts(session) -> None:
    from datetime import date
    from app.models.child import Child
    from app.models.job import Job
    from app.models.recording import Recording
    from app.models.speaker import SpeakerProfile, VoiceVersion
    from app.services.tts_config import save_tts_config
    from app.workers.runner import repair_pending_work

    save_tts_config(session, protocol='mimo', base_url='https://api.xiaomimimo.com/v1', api_key_value='key', model='mimo-v2.5-tts', voice='Chloe', speed=1.0)
    child = Child(display_name='孩子', slug='repair-child'); session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=date.today(), language_type='english', status='transcode_failed', source_path='/data/source.mp4')
    assembling = Recording(child_id=child.id, reading_date=date.today(), language_type='chinese', status='assembling')
    transcoding = Recording(child_id=child.id, reading_date=date.today(), language_type='chinese', status='transcoding', source_path='/data/chinese-source.mp4')
    speaker = SpeakerProfile(display_name='我的声音'); session.add_all([recording, assembling, transcoding, speaker]); session.flush()
    voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='录音', status='failed', failure_code='VOICE_SAMPLE_UNSUPPORTED', reference_audio_path='/data/sample.webm')
    session.add(voice); session.commit()

    repair_pending_work(session)

    assert recording.status == 'transcoding'
    assert voice.status == 'processing'
    assert session.query(Job).filter_by(type='transcode_video', entity_id=recording.id, status='queued').count() == 1
    assert session.query(Job).filter_by(type='assemble_video', entity_id=assembling.id, status='queued').count() == 1
    assert session.query(Job).filter_by(type='transcode_video', entity_id=transcoding.id, status='queued').count() == 1
    assert session.query(Job).filter_by(type='normalize_voice_sample', entity_id=voice.id, status='queued').count() == 1


def test_repair_does_not_restart_an_exhausted_media_failure(session) -> None:
    from datetime import date
    from app.models.child import Child
    from app.models.job import Job
    from app.models.recording import Recording
    from app.workers.runner import repair_pending_work

    child = Child(display_name='孩子', slug='exhausted-media-child'); session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=date.today(), language_type='english', status='transcode_failed', source_path='/data/source.mp4')
    session.add(recording); session.flush()
    job = Job(type='transcode_video', entity_id=recording.id, status='failed', attempts=5, max_attempts=5)
    session.add(job); session.commit()

    repair_pending_work(session)
    session.refresh(recording); session.refresh(job)

    assert recording.status == 'transcode_failed'
    assert job.status == 'failed'
    assert session.query(Job).filter_by(type='transcode_video', entity_id=recording.id).count() == 1
