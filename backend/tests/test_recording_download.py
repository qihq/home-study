from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient


def test_compressed_video_download_requires_login(client: TestClient) -> None:
    assert client.get('/api/recordings/not-a-public-id/download/720p').status_code == 401


def test_worker_marks_completed_video_job_succeeded(session, video_fixture, tmp_path: Path) -> None:
    from app.models.child import Child
    from app.models.job import Job
    from app.models.recording import Recording, RecordingChunk
    from app.workers.runner import run_once
    import hashlib

    child = Child(display_name='孩子', slug='runner-child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=date.today(), language_type='chinese', status='assembling')
    session.add(recording); session.flush()
    source = tmp_path / 'runner-chunk.mp4'; source.write_bytes(video_fixture)
    session.add(RecordingChunk(recording_id=recording.id, sequence=0, size_bytes=len(video_fixture), sha256=hashlib.sha256(video_fixture).hexdigest(), mime_type='video/mp4', path=str(source)))
    job = Job(type='assemble_video', entity_id=recording.id)
    session.add(job); session.commit()

    assert run_once(session, 'worker-test') is True
    session.refresh(job)
    assert job.status == 'succeeded'
