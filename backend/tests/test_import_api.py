from fastapi.testclient import TestClient


def test_text_file_upload_returns_editable_candidates(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.post('/api/imports', headers=headers, files={'file': ('words.txt', b'Apple\nbanana\n', 'text/plain')})

    assert response.status_code == 201
    assert response.json()['items'][0]['display_text'] == 'Apple'
    assert response.json()['items'][0]['source_location'] == 'line:1'
