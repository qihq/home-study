from fastapi.testclient import TestClient
import json
from datetime import datetime, timezone


def test_health_reports_database_media_and_ffmpeg(client: TestClient) -> None:
    response = client.get('/api/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['database'] is True
    assert payload['media'] is True
    assert payload['ffmpeg'] is True
    assert isinstance(payload['vaapi'], bool)
    assert payload['worker_state'] == 'offline'


def test_health_reports_busy_worker_without_false_offline(client: TestClient, tmp_path, monkeypatch) -> None:
    from app.core.config import get_settings

    heartbeat = get_settings().data_dir / 'worker-heartbeat.json'
    heartbeat.write_text(json.dumps({
        'worker_id': 'worker-busy',
        'busy': True,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }), encoding='utf-8')

    payload = client.get('/api/health').json()

    assert payload['worker'] is True
    assert payload['worker_state'] == 'busy'
    assert payload['worker_updated_at'] is not None


def test_health_reports_ffmpeg_false_instead_of_failing_when_the_probe_times_out(
    client: TestClient, monkeypatch,
) -> None:
    """A stalled ffmpeg probe must degrade to ``ffmpeg: false``, not an HTTP 500."""
    import subprocess

    from app.api import health

    monkeypatch.setattr(health, '_ffmpeg_probe', None)
    monkeypatch.setattr(health.shutil, 'which', lambda _name: '/usr/bin/ffmpeg')

    def timing_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd='ffmpeg', timeout=health.FFMPEG_PROBE_TIMEOUT_SECONDS)

    monkeypatch.setattr(health.subprocess, 'run', timing_out)

    response = client.get('/api/health')

    assert response.status_code == 200
    assert response.json()['ffmpeg'] is False


def test_health_probes_ffmpeg_once_per_cache_window(client: TestClient, monkeypatch) -> None:
    """The health endpoint is polled continuously; ffmpeg must not be spawned every time."""
    from app.api import health

    monkeypatch.setattr(health, '_ffmpeg_probe', None)
    probes: list[str] = []
    real_probe = health._probe_ffmpeg
    monkeypatch.setattr(health, '_probe_ffmpeg', lambda: (probes.append('probe'), real_probe())[1])

    payloads = [client.get('/api/health').json() for _ in range(3)]

    assert all(payload['ffmpeg'] is True for payload in payloads)
    assert len(probes) == 1
