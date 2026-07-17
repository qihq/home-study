import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.child import Child
from app.models.recording import Recording, RecordingChunk


class ChunkConflict(Exception): pass


def create_recording(session: Session, language_type: str) -> Recording:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        child = Child(display_name='孩子', slug='default-child')
        session.add(child); session.flush()
    recording = Recording(child_id=child.id, language_type=language_type, reading_date=datetime.now().date(), status='recording')
    session.add(recording); session.commit(); session.refresh(recording)
    return recording


def upload_chunk(session: Session, recording: Recording, sequence: int, body: bytes, digest: str, mime_type: str) -> bool:
    actual = hashlib.sha256(body).hexdigest()
    if actual != digest: raise ValueError('CHUNK_HASH_MISMATCH')
    existing = session.scalar(select(RecordingChunk).where(RecordingChunk.recording_id == recording.id, RecordingChunk.sequence == sequence))
    if existing:
        if existing.sha256 != digest: raise ChunkConflict()
        return True
    directory = get_settings().uploads_dir / 'recordings' / recording.id / 'chunks'; directory.mkdir(parents=True, exist_ok=True)
    partial, final = directory / f'{sequence}.part', directory / f'{sequence}.bin'
    partial.write_bytes(body); partial.replace(final)
    session.add(RecordingChunk(recording_id=recording.id, sequence=sequence, size_bytes=len(body), sha256=digest, mime_type=mime_type, path=str(final)))
    session.commit(); return False


def missing_sequences(session: Session, recording_id: str, final_count: int) -> list[int]:
    received = set(session.scalars(select(RecordingChunk.sequence).where(RecordingChunk.recording_id == recording_id)).all())
    return [number for number in range(final_count) if number not in received]


def delete_recording(session: Session, recording: Recording) -> None:
    paths = [Path(chunk.path) for chunk in session.scalars(select(RecordingChunk).where(RecordingChunk.recording_id == recording.id))]
    paths.extend(Path(path) for path in (recording.source_path, recording.compressed_path) if path)
    for path in paths:
        path.unlink(missing_ok=True)
    upload_dir = get_settings().uploads_dir / 'recordings' / recording.id
    if upload_dir.exists():
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)
    if recording.source_path:
        source_dir = Path(recording.source_path).parent
        if source_dir.exists():
            import shutil
            shutil.rmtree(source_dir, ignore_errors=True)
    session.delete(recording)
    session.commit()
