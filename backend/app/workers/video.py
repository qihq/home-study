import json
import shutil
import struct
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


def _mp4_box_types(path: Path) -> set[bytes]:
    data = path.read_bytes()
    types: set[bytes] = set()
    offset = 0
    while offset + 8 <= len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        header_size = 8
        if size == 1:
            if offset + 16 > len(data):
                raise MediaError('MP4_BOX_TRUNCATED')
            size = struct.unpack('>Q', data[offset + 8:offset + 16])[0]
            header_size = 16
        elif size == 0:
            size = len(data) - offset
        if size < header_size or offset + size > len(data):
            raise MediaError('MP4_BOX_TRUNCATED')
        types.add(data[offset + 4:offset + 8])
        offset += size
    if offset != len(data):
        raise MediaError('MP4_BOX_TRUNCATED')
    return types


def _fragmented_mp4_epochs(chunks: list[RecordingChunk]) -> list[list[RecordingChunk]] | None:
    if not all(chunk.mime_type.lower().startswith('video/mp4') for chunk in chunks):
        return None
    box_types = [_mp4_box_types(Path(chunk.path)) for chunk in chunks]
    if not any(b'moof' in types for types in box_types):
        return None
    epochs: list[list[RecordingChunk]] = []
    for chunk, types in zip(chunks, box_types, strict=True):
        if b'moov' in types:
            if not {b'moof', b'mdat'} <= types:
                raise MediaError('FMP4_INITIALIZATION_INVALID')
            epochs.append([chunk])
        elif {b'moof', b'mdat'} <= types and b'ftyp' not in types:
            if not epochs:
                raise MediaError('FMP4_INITIALIZATION_MISSING')
            epochs[-1].append(chunk)
        else:
            raise MediaError('FMP4_CHUNK_LAYOUT_INVALID')
    return epochs


def _join_chunk_bytes(chunks: list[RecordingChunk], target: Path) -> None:
    with target.open('wb') as output:
        for chunk in chunks:
            with Path(chunk.path).open('rb') as source:
                shutil.copyfileobj(source, output)


def _concat_files(paths: list[Path], manifest: Path, target: Path) -> None:
    entries = ["file '" + str(path.resolve()).replace("'", "'\\''") + "'" for path in paths]
    manifest.write_text('\n'.join(entries) + '\n', encoding='utf-8')
    _run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(manifest), '-c', 'copy', '-f', 'mp4', str(target)])


def process_assemble_video(session: Session, recording_id: str, report_progress=lambda _value: None) -> None:
    recording = _recording_or_error(session, recording_id)
    chunks = list(session.scalars(select(RecordingChunk).where(RecordingChunk.recording_id == recording_id).order_by(RecordingChunk.sequence)))
    if not chunks or [chunk.sequence for chunk in chunks] != list(range(len(chunks))):
        recording.status = 'assemble_failed'; session.commit(); return
    output_dir = get_settings().videos_dir / recording.child_id / str(recording.reading_date) / recording.language_type / recording.id
    output_dir.mkdir(parents=True, exist_ok=True)
    partial = output_dir / 'source.mp4.part'; source = output_dir / 'source.mp4'
    temporary_epochs: list[Path] = []
    try:
        report_progress(20)
        if len(chunks) == 1:
            shutil.copyfile(chunks[0].path, partial)
        else:
            epochs = _fragmented_mp4_epochs(chunks)
            manifest = output_dir / 'chunks.concat.txt'
            if epochs and len(epochs) == 1:
                _join_chunk_bytes(epochs[0], partial)
            elif epochs:
                for index, epoch in enumerate(epochs):
                    epoch_path = output_dir / f'epoch-{index}.mp4.part'
                    _join_chunk_bytes(epoch, epoch_path)
                    temporary_epochs.append(epoch_path)
                _concat_files(temporary_epochs, manifest, partial)
            else:
                _concat_files([Path(chunk.path) for chunk in chunks], manifest, partial)
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
    finally:
        for path in temporary_epochs:
            path.unlink(missing_ok=True)


def transcode_recording(recording: Recording) -> Path:
    if not recording.source_path:
        raise MediaError('SOURCE_MISSING')
    source = Path(recording.source_path); target = source.with_name('720p.mp4'); partial = target.with_suffix('.mp4.part')
    _run([
        'ffmpeg', '-y', '-i', str(source),
        '-vf', r'scale=w=min(1280\,iw):h=min(720\,ih):force_original_aspect_ratio=decrease:force_divisible_by=2:in_range=pc:out_range=tv',
        '-r', '30', '-c:v', 'libx264', '-profile:v', 'main', '-level:v', '3.1',
        '-preset', 'medium', '-crf', '27', '-maxrate', '900k', '-bufsize', '1800k',
        '-g', '60', '-keyint_min', '30', '-pix_fmt', 'yuv420p',
        '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
        '-c:a', 'aac', '-b:a', '80k', '-movflags', '+faststart', '-f', 'mp4', str(partial),
    ])
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
