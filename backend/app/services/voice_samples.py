import base64
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class VoiceSampleError(Exception):
    pass


@dataclass(frozen=True)
class VoiceSampleMetadata:
    duration_ms: int
    size_bytes: int


def _probe(path: Path) -> dict:
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
            check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise VoiceSampleError('VOICE_SAMPLE_UNSUPPORTED') from error


def validate_normalized_wav(path: Path) -> VoiceSampleMetadata:
    probe = _probe(path)
    audio_streams = [stream for stream in probe.get('streams', []) if stream.get('codec_type') == 'audio']
    if len(audio_streams) != 1:
        raise VoiceSampleError('VOICE_SAMPLE_UNSUPPORTED')
    duration_seconds = float(probe.get('format', {}).get('duration', 0))
    if duration_seconds < 3:
        raise VoiceSampleError('VOICE_SAMPLE_TOO_SHORT')
    if duration_seconds > 30:
        raise VoiceSampleError('VOICE_SAMPLE_TOO_LONG')
    encoded_size = len(base64.b64encode(path.read_bytes()))
    if encoded_size > 10 * 1024 * 1024:
        raise VoiceSampleError('VOICE_SAMPLE_BASE64_TOO_LARGE')
    return VoiceSampleMetadata(duration_ms=round(duration_seconds * 1000), size_bytes=path.stat().st_size)


def normalize_voice_sample(source: Path, target: Path) -> VoiceSampleMetadata:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix('.wav.part')
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', str(source), '-map', '0:a:0', '-t', '30', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', '-f', 'wav', str(partial)],
            check=True, capture_output=True,
        )
        metadata = validate_normalized_wav(partial)
        partial.replace(target)
        return metadata
    except (OSError, subprocess.CalledProcessError) as error:
        raise VoiceSampleError('VOICE_SAMPLE_UNSUPPORTED') from error
    finally:
        partial.unlink(missing_ok=True)
