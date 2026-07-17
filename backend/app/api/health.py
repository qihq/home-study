import shutil
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=['health'])


def can_write(directory: Path) -> bool:
    probe = directory / '.healthcheck'
    try:
        probe.write_text('ok', encoding='ascii')
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def has_ffmpeg() -> bool:
    executable = shutil.which('ffmpeg')
    if executable is None:
        return False
    completed = subprocess.run(
        [executable, '-version'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return completed.returncode == 0


def has_vaapi() -> bool:
    return Path('/dev/dri').exists()


@router.get('/health')
def health() -> dict[str, bool | str]:
    settings = get_settings()
    heartbeat = settings.data_dir / 'worker-heartbeat.json'
    worker = False
    if heartbeat.is_file():
        try:
            updated = datetime.fromisoformat(json.loads(heartbeat.read_text(encoding='utf-8'))['updated_at'])
            worker = (datetime.now(timezone.utc) - updated).total_seconds() < 15
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            worker = False
    return {
        'status': 'ok',
        'database': True,
        'media': can_write(settings.data_dir),
        'ffmpeg': has_ffmpeg(),
        'vaapi': has_vaapi(),
        'worker': worker,
    }
