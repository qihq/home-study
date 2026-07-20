import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.db.session import get_session_factory
from app.services.jobs import renew_job_lease


def touch_worker_heartbeat(data_dir: Path, worker_id: str, *, busy: bool) -> None:
    target = data_dir / 'worker-heartbeat.json'
    partial = target.with_suffix('.json.part')
    partial.write_text(json.dumps({
        'worker_id': worker_id,
        'busy': busy,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }), encoding='utf-8')
    partial.replace(target)


class WorkerActivity:
    def __init__(self, data_dir: Path, worker_id: str, job_id: str, interval_seconds: float = 5) -> None:
        self.data_dir = data_dir
        self.worker_id = worker_id
        self.job_id = job_id
        self.interval_seconds = interval_seconds
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f'worker-activity-{job_id}', daemon=True)

    def start(self) -> None:
        self._touch()
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=self.interval_seconds + 1)

    def _touch(self) -> None:
        touch_worker_heartbeat(self.data_dir, self.worker_id, busy=True)
        with get_session_factory()() as session:
            renew_job_lease(session, self.job_id, self.worker_id, datetime.now(timezone.utc))

    def _run(self) -> None:
        while not self._stopped.wait(self.interval_seconds):
            try:
                self._touch()
            except Exception:
                # Status renewal failure must not terminate active media work.
                continue
