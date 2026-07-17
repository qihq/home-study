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
    speaker = SpeakerProfile(display_name='我的声音'); session.add_all([recording, speaker]); session.flush()
    voice = VoiceVersion(speaker_profile_id=speaker.id, display_name='录音', status='failed', failure_code='VOICE_SAMPLE_UNSUPPORTED', reference_audio_path='/data/sample.webm')
    session.add(voice); session.commit()

    repair_pending_work(session)

    assert recording.status == 'transcoding'
    assert voice.status == 'processing'
    assert session.query(Job).filter_by(type='transcode_video', entity_id=recording.id, status='queued').count() == 1
    assert session.query(Job).filter_by(type='normalize_voice_sample', entity_id=voice.id, status='queued').count() == 1
