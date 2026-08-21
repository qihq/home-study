"""Scheduled local dictionary updates.

Rebuilds the local SQLite dictionary from upstream sources (ECDICT + CC-CEDICT)
on an interval, throttled by a marker file under the data directory. The actual
build runs in a subprocess (the standalone ``scripts/build_local_dictionary.py``
next to the backend checkout) so memory pressure and long CSV parsing stay
outside the worker, and the output file is replaced atomically by the builder.

The version string derives from the upstream checksums, so the dictionary
fingerprint only changes when content changes — which automatically invalidates
cached ``dictionary_entries``.

The download/checksum helpers are inlined here (instead of importing the
``scripts`` package) because ``scripts`` is not part of the installed backend
wheel; the builder is invoked by path via ``APP_DICTIONARY_BUILDER_PATH``.
"""

import hashlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job
from app.services.jobs import enqueue_once

UPDATE_JOB_TYPE = 'update_dictionary'
UPDATE_JOB_ENTITY = 'local'
BUILD_TIMEOUT_SECONDS = 1800

ECDICT_DOWNLOAD_URL = 'https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv'
CEDICT_DOWNLOAD_URL = 'https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz'
USER_AGENT = 'family-learning/1.0 (dictionary auto-update)'


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _marker_path() -> Path:
    return get_settings().data_dir / 'dictionary-update.last'


def _write_marker(path: Path, value: datetime) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value.isoformat())
    except OSError:
        pass


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def ensure_source(path: Path | None, filename: str, url: str, download_flag: bool, cache_dir: Path) -> Path:
    if path is not None:
        return path
    cached = cache_dir / filename
    if cached.is_file():
        return cached
    if not download_flag:
        raise RuntimeError(f'missing source {filename} and download disabled')
    cache_dir.mkdir(parents=True, exist_ok=True)
    partial = cached.with_suffix(cached.suffix + '.part')
    with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=600) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f'empty download from {url}')
    partial.write_bytes(data)
    partial.replace(cached)
    return cached


def enqueue_if_due(session: Session, now: datetime | None = None) -> Job | None:
    """Enqueue one update job when the interval has elapsed; never raises."""
    try:
        settings = get_settings()
        if not settings.dictionary_auto_update:
            return None
        current = now or datetime.now(timezone.utc)
        marker = _marker_path()
        try:
            if marker.is_file():
                last = _as_utc(datetime.fromisoformat(marker.read_text().strip()))
                if (current - last) < timedelta(days=settings.dictionary_update_interval_days):
                    return None
        except (OSError, ValueError):
            pass
        job = enqueue_once(session, UPDATE_JOB_TYPE, UPDATE_JOB_ENTITY)
        session.commit()
        _write_marker(marker, current)
        return job
    except Exception:
        return None


def process_update_dictionary(session: Session, entity_id: str, report_progress=lambda _value: None) -> None:
    """Rebuild the local dictionary from (downloaded) upstream sources."""
    settings = get_settings()
    cache_dir = settings.data_dir / 'dictionary-sources'
    target = settings.local_dictionary_path
    builder = Path(settings.dictionary_builder_path)
    report_progress(10)
    ecdict = ensure_source(None, 'ecdict.csv', ECDICT_DOWNLOAD_URL, True, cache_dir)
    cedict = ensure_source(None, 'cedict_1_0_ts_utf-8_mdbg.txt.gz', CEDICT_DOWNLOAD_URL, True, cache_dir)
    version = f'auto-{checksum(ecdict)[:12]}-{checksum(cedict)[:12]}'
    report_progress(30)
    try:
        subprocess.run(
            [
                sys.executable, str(builder),
                '--ecdict', str(ecdict), '--cedict', str(cedict),
                '--output', str(target), '--version', version,
            ],
            check=True, capture_output=True, text=True, timeout=BUILD_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        detail = getattr(error, 'stderr', None) or str(error)
        raise RuntimeError(f'DICTIONARY_UPDATE_FAILED: {detail[:500]}') from error
    report_progress(95)
    _write_marker(_marker_path(), datetime.now(timezone.utc))
