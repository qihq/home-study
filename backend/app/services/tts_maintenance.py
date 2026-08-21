"""Stale TTS asset cleanup.

Audio assets accumulate under ``<data>/tts``. This module deletes ``TtsAsset``
rows that are unreferenced (not linked from word items or learning-item audio
rows) and older than :data:`STALE_AFTER`, together with their files on disk.
It runs at most once per :data:`CLEANUP_INTERVAL` from the worker repair loop.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.learning_item import LearningItem
from app.models.learning_item_audio import LearningItemAudio
from app.models.tts_asset import TtsAsset

CLEANUP_INTERVAL = timedelta(hours=24)
STALE_AFTER = timedelta(days=90)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _marker_path() -> Path:
    return get_settings().data_dir / 'tts-cleanup.last'


def maybe_cleanup_stale_tts_assets(session: Session, now: datetime | None = None) -> dict:
    """Delete unreferenced stale TTS assets; never raises.

    Returns ``{'skipped': bool, 'deleted_assets': int, 'deleted_files': int}``.
    """
    try:
        current = now or datetime.now(timezone.utc)
        marker = _marker_path()
        try:
            if marker.is_file():
                last = _as_utc(datetime.fromisoformat(marker.read_text().strip()))
                if (current - last) < CLEANUP_INTERVAL:
                    return {'skipped': True, 'deleted_assets': 0, 'deleted_files': 0}
        except (OSError, ValueError):
            pass

        cutoff = current - STALE_AFTER
        referenced = set(session.scalars(select(LearningItem.tts_asset_id).where(LearningItem.tts_asset_id.is_not(None))))
        referenced.update(session.scalars(select(LearningItemAudio.tts_asset_id).where(LearningItemAudio.tts_asset_id.is_not(None))))
        all_assets = list(session.scalars(select(TtsAsset)))

        to_delete = [
            asset for asset in all_assets
            if asset.id not in referenced and _as_utc(asset.created_at) < cutoff
        ]
        remaining = len(all_assets) - len(to_delete)
        max_assets = get_settings().tts_max_assets
        if remaining > max_assets:
            oldest_unreferenced = sorted(
                (asset for asset in all_assets if asset.id not in referenced and asset not in to_delete),
                key=lambda asset: _as_utc(asset.created_at),
            )
            to_delete.extend(oldest_unreferenced[:remaining - max_assets])

        deleted_assets, deleted_files = 0, 0
        tts_root = get_settings().tts_dir.resolve()
        for asset in to_delete:
            path = Path(asset.path)
            if path.is_file() and path.resolve().is_relative_to(tts_root):
                path.unlink(missing_ok=True)
                deleted_files += 1
            session.delete(asset)
            deleted_assets += 1
        session.commit()
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(current.isoformat())
        except OSError:
            pass
        return {'skipped': False, 'deleted_assets': deleted_assets, 'deleted_files': deleted_files}
    except Exception:
        session.rollback()
        return {'skipped': True, 'deleted_assets': 0, 'deleted_files': 0}
