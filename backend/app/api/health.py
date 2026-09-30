import shutil
import subprocess
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=['health'])

# Spawning ffmpeg costs about a second on the NAS with a cold page cache, and the health
# endpoint is polled continuously. Probing on every request made an I/O stall report
# ffmpeg as missing and returned HTTP 500, so the result is cached for a short window.
FFMPEG_PROBE_TIMEOUT_SECONDS = 15.0
FFMPEG_PROBE_CACHE_SECONDS = 60.0
_ffmpeg_probe: tuple[float, bool] | None = None


def can_write(directory: Path) -> bool:
    probe = directory / '.healthcheck'
    try:
        probe.write_text('ok', encoding='ascii')
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _probe_ffmpeg() -> bool:
    executable = shutil.which('ffmpeg')
    if executable is None:
        return False
    try:
        completed = subprocess.run(
            [executable, '-version'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=FFMPEG_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        # A stalled probe means "not usable right now", never an unhandled 500.
        return False
    return completed.returncode == 0


def has_ffmpeg() -> bool:
    global _ffmpeg_probe
    now = time.monotonic()
    if _ffmpeg_probe is not None and now - _ffmpeg_probe[0] < FFMPEG_PROBE_CACHE_SECONDS:
        return _ffmpeg_probe[1]
    result = _probe_ffmpeg()
    _ffmpeg_probe = (now, result)
    return result


def has_vaapi() -> bool:
    return Path('/dev/dri').exists()


@router.get('/health')
def health() -> dict[str, bool | str | None]:
    settings = get_settings()
    heartbeat = settings.data_dir / 'worker-heartbeat.json'
    worker = False
    worker_state = 'offline'
    updated: datetime | None = None
    if heartbeat.is_file():
        try:
            heartbeat_data = json.loads(heartbeat.read_text(encoding='utf-8'))
            updated = datetime.fromisoformat(heartbeat_data['updated_at'])
            worker = (datetime.now(timezone.utc) - updated).total_seconds() < 15
            if worker:
                worker_state = 'busy' if heartbeat_data.get('busy') else 'online'
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            worker = False
            worker_state = 'offline'
            updated = None
    return {
        'status': 'ok',
        'database': True,
        'media': can_write(settings.data_dir),
        'ffmpeg': has_ffmpeg(),
        'vaapi': has_vaapi(),
        'worker': worker,
        'worker_state': worker_state,
        'worker_updated_at': updated.isoformat() if updated else None,
    }
