from fastapi.testclient import TestClient


def test_health_reports_database_media_and_ffmpeg(client: TestClient) -> None:
    response = client.get('/api/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['database'] is True
    assert payload['media'] is True
    assert payload['ffmpeg'] is True
    assert isinstance(payload['vaapi'], bool)
