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
