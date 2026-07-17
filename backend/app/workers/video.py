import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.recording import Recording, RecordingChunk
from app.services.jobs import enqueue_once


class MediaError(Exception):
    pass


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise MediaError(completed.stderr[-500:])
    return completed


def probe_video(path: Path) -> dict:
    completed = _run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', str(path)])
    info = json.loads(completed.stdout)
    stream_types = {stream['codec_type'] for stream in info.get('streams', [])}
    duration = float(info.get('format', {}).get('duration', 0))
    if not {'video', 'audio'} <= stream_types or duration <= 0:
        raise MediaError('SOURCE_INVALID')
    return {'duration_ms': round(duration * 1000)}


def _recording_or_error(session: Session, recording_id: str) -> Recording:
    recording = session.get(Recording, recording_id)
    if recording is None:
        raise MediaError('RECORDING_NOT_FOUND')
    return recording


def process_assemble_video(session: Session, recording_id: str, report_progress=lambda _value: None) -> None:
    recording = _recording_or_error(session, recording_id)
    chunks = list(session.scalars(select(RecordingChunk).where(RecordingChunk.recording_id == recording_id).order_by(RecordingChunk.sequence)))
    if not chunks or [chunk.sequence for chunk in chunks] != list(range(len(chunks))):
        recording.status = 'assemble_failed'; session.commit(); return
    output_dir = get_settings().videos_dir / recording.child_id / str(recording.reading_date) / recording.language_type / recording.id
    output_dir.mkdir(parents=True, exist_ok=True)
    partial = output_dir / 'source.mp4.part'; source = output_dir / 'source.mp4'
    try:
        report_progress(20)
        if len(chunks) == 1:
            shutil.copyfile(chunks[0].path, partial)
        else:
            manifest = output_dir / 'chunks.concat.txt'
            # ffconcat escapes single quotes by closing and reopening the quoted path.
            entries = ["file '" + str(Path(chunk.path).resolve()).replace("'", "'\\''") + "'" for chunk in chunks]
            manifest.write_text('\n'.join(entries) + '\n', encoding='utf-8')
            _run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(manifest), '-c', 'copy', '-f', 'mp4', str(partial)])
        report_progress(65)
        details = probe_video(partial)
        partial.replace(source)
        recording.source_path = str(source)
        recording.verified_duration_ms = details['duration_ms']
        recording.source_validated_at = datetime.now(timezone.utc)
        recording.status = 'transcoding'
        already_official = session.scalar(select(Recording).where(Recording.child_id == recording.child_id, Recording.reading_date == recording.reading_date, Recording.language_type == recording.language_type, Recording.is_official.is_(True)))
        recording.is_official = already_official is None
        enqueue_once(session, 'transcode_video', recording.id)
        session.commit()
    except MediaError:
        partial.unlink(missing_ok=True)
        recording.status = 'assemble_failed'; session.commit()


def transcode_recording(recording: Recording) -> Path:
    if not recording.source_path:
        raise MediaError('SOURCE_MISSING')
    source = Path(recording.source_path); target = source.with_name('720p.mp4'); partial = target.with_suffix('.mp4.part')
    _run(['ffmpeg', '-y', '-i', str(source), '-vf', 'scale=w=1280:h=720:force_original_aspect_ratio=decrease', '-r', '30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-b:v', '1500k', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-f', 'mp4', str(partial)])
    probe_video(partial)
    partial.replace(target)
    return target


def process_transcode_video(session: Session, recording_id: str, report_progress=lambda _value: None) -> None:
    recording = _recording_or_error(session, recording_id)
    try:
        report_progress(20)
        target = transcode_recording(recording)
        report_progress(90)
        recording.compressed_path = str(target); recording.status = 'ready'
    except MediaError:
        recording.status = 'transcode_failed'
    session.commit()
