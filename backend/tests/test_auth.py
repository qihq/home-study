from fastapi.testclient import TestClient


def test_login_sets_http_only_session_cookie(client: TestClient, admin_user) -> None:
    response = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})

    assert response.status_code == 200
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie
    assert 'samesite=lax' in cookie


def test_private_route_rejects_anonymous_user(client: TestClient) -> None:
    assert client.get('/api/me').status_code == 401
