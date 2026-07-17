from fastapi.testclient import TestClient


def test_initial_setup_creates_first_admin_only_once(client: TestClient) -> None:
    payload = {'username': 'parent', 'password': 'correct horse'}

    first = client.post('/api/setup/initial-admin', json=payload)
    second = client.post('/api/setup/initial-admin', json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()['detail']['code'] == 'INITIAL_ADMIN_EXISTS'


def test_setup_status_reports_whether_an_admin_exists(client: TestClient) -> None:
    assert client.get('/api/setup/status').json() == {'needs_initial_admin': True}
    client.post('/api/setup/initial-admin', json={'username': 'parent', 'password': 'correct horse'})
    assert client.get('/api/setup/status').json() == {'needs_initial_admin': False}
