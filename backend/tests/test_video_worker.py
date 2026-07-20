import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
import pytest



def test_verified_source_makes_first_recording_official(session, video_fixture: bytes, tmp_path: Path) -> None:
    from app.models.recording import Recording, RecordingChunk
    from app.workers.video import process_assemble_video
    from app.models.child import Child

    child = Child(display_name='孩子', slug='child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=datetime.now().date(), language_type='chinese', status='assembling')
    session.add(recording); session.flush()
    path = tmp_path / 'test-chunk.mp4'; path.write_bytes(video_fixture)
    session.add(RecordingChunk(recording_id=recording.id, sequence=0, size_bytes=len(video_fixture), sha256=hashlib.sha256(video_fixture).hexdigest(), mime_type='video/mp4', path=str(path)))
    session.commit()

    process_assemble_video(session, recording.id)
    session.refresh(recording)

    assert recording.source_validated_at is not None
    assert recording.is_official is True
    from app.models.job import Job
    assert session.query(Job).filter_by(type='transcode_video', entity_id=recording.id).count() == 1


def test_assembly_remuxes_multiple_contiguous_chunks(session, video_fixture: bytes, tmp_path: Path) -> None:
    from app.models.recording import Recording, RecordingChunk
    from app.workers.video import process_assemble_video
    from app.models.child import Child

    child = Child(display_name='孩子', slug='child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=datetime.now().date(), language_type='chinese', status='assembling')
    session.add(recording); session.flush()
    for sequence in range(2):
        path = tmp_path / f'test-chunk-{sequence}.mp4'; path.write_bytes(video_fixture)
        session.add(RecordingChunk(recording_id=recording.id, sequence=sequence, size_bytes=len(video_fixture), sha256=hashlib.sha256(video_fixture).hexdigest(), mime_type='video/mp4', path=str(path)))
    session.commit()

    process_assemble_video(session, recording.id)
    session.refresh(recording)

    assert recording.source_validated_at is not None
    assert recording.verified_duration_ms == pytest.approx(2_000, abs=100)


def test_assembly_preserves_dependent_fragmented_mp4_duration(session, fragmented_video_chunks: list[bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    from app.models.child import Child
    from app.models.recording import Recording, RecordingChunk
    from app.workers.video import process_assemble_video

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    child = Child(display_name='孩子', slug='fragmented-child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=datetime.now().date(), language_type='chinese', status='assembling')
    session.add(recording); session.flush()
    for sequence, body in enumerate(fragmented_video_chunks):
        path = tmp_path / f'fragment-{sequence}.bin'
        path.write_bytes(body)
        session.add(RecordingChunk(recording_id=recording.id, sequence=sequence, size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), mime_type='video/mp4', path=str(path)))
    session.commit()

    process_assemble_video(session, recording.id)
    session.refresh(recording)

    assert recording.status == 'transcoding'
    assert recording.source_validated_at is not None
    assert recording.verified_duration_ms == pytest.approx(12_000, abs=250)
    assert Path(recording.source_path).read_bytes() == b''.join(fragmented_video_chunks)
    get_settings.cache_clear()


def test_assembly_preserves_multiple_fragmented_mp4_epochs(session, fragmented_video_chunks: list[bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    from app.models.child import Child
    from app.models.recording import Recording, RecordingChunk
    from app.workers.video import process_assemble_video

    monkeypatch.setenv('APP_DATA_DIR', str(tmp_path / 'data'))
    get_settings.cache_clear()
    child = Child(display_name='孩子', slug='camera-switch-child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=datetime.now().date(), language_type='english', status='assembling')
    session.add(recording); session.flush()
    bodies = fragmented_video_chunks + fragmented_video_chunks
    for sequence, body in enumerate(bodies):
        path = tmp_path / f'camera-switch-fragment-{sequence}.bin'
        path.write_bytes(body)
        session.add(RecordingChunk(recording_id=recording.id, sequence=sequence, size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), mime_type='video/mp4', path=str(path)))
    session.commit()

    process_assemble_video(session, recording.id)
    session.refresh(recording)

    assert recording.status == 'transcoding'
    assert recording.verified_duration_ms == pytest.approx(24_000, abs=500)
    get_settings.cache_clear()


def test_transcode_failure_keeps_source_completion(session, video_fixture: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.recording import Recording
    from app.workers.video import MediaError, process_transcode_video
    from app.models.child import Child

    child = Child(display_name='孩子', slug='child')
    session.add(child); session.flush()
    recording = Recording(child_id=child.id, reading_date=datetime.now().date(), language_type='english', status='transcoding', source_validated_at=datetime.now())
    session.add(recording); session.commit()
    monkeypatch.setattr('app.workers.video.transcode_recording', lambda *_: (_ for _ in ()).throw(MediaError('encoder failed')))

    process_transcode_video(session, recording.id)
    session.refresh(recording)

    assert recording.source_validated_at is not None
    assert recording.status == 'transcode_failed'


def test_transcode_writes_mp4_even_when_temporary_name_ends_in_part(session, video_fixture: bytes, tmp_path: Path) -> None:
    from app.models.child import Child
    from app.models.recording import Recording
    from app.workers.video import process_transcode_video

    child = Child(display_name='孩子', slug='transcode-part'); session.add(child); session.flush()
    source = tmp_path / 'source.mp4'; source.write_bytes(video_fixture)
    recording = Recording(child_id=child.id, reading_date=datetime.now().date(), language_type='english', status='transcoding', source_path=str(source), source_validated_at=datetime.now())
    session.add(recording); session.commit()

    process_transcode_video(session, recording.id)
    session.refresh(recording)

    assert recording.status == 'ready'
    assert Path(recording.compressed_path).is_file()
    completed = subprocess.run([
        'ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height',
        '-of', 'json', recording.compressed_path,
    ], text=True, capture_output=True, check=True)
    video = next(stream for stream in json.loads(completed.stdout)['streams'] if stream['codec_type'] == 'video')
    assert (video['width'], video['height']) == (320, 240)
