from fastapi.testclient import TestClient


def test_confirmed_word_list_appears_in_list_endpoint(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    created = client.post('/api/word-lists', json={'title': '第一周', 'pasted_text': 'Apple\nbanana'}, headers=headers)
    client.post(f"/api/word-lists/{created.json()['id']}/confirm", headers=headers)

    response = client.get('/api/word-lists', headers=headers)

    assert response.status_code == 200
    assert response.json()[0]['title'] == '第一周'
    assert response.json()[0]['items'] == ['Apple', 'banana']


def test_deleting_a_list_with_dictation_history_archives_and_hides_it(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    created = client.post('/api/word-lists', json={'title': '旧错误单词本', 'pasted_text': 'wrong'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{created['id']}/confirm", headers=headers).json()
    client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id']}, headers=headers)

    deleted = client.delete(f"/api/word-lists/{created['id']}", headers=headers)

    assert deleted.status_code == 204
    assert all(item['id'] != created['id'] for item in client.get('/api/word-lists', headers=headers).json())


def test_parent_can_force_one_word_to_use_configured_native_pronunciation(client: TestClient, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    created = client.post('/api/word-lists', json={'title': '歧义词', 'pasted_text': 'use'}, headers=headers).json()
    client.post(f"/api/word-lists/{created['id']}/confirm", headers=headers)
    item = client.get('/api/word-lists', headers=headers).json()[0]['item_details'][0]

    changed = client.patch(f"/api/word-items/{item['id']}/pronunciation", headers=headers, json={'pronunciation_source': 'configured'})

    assert changed.status_code == 200
    assert changed.json()['pronunciation_source'] == 'configured'
    assert changed.json()['audio_ready'] is False
