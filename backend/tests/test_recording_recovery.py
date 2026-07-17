import hashlib


def test_received_chunk_list_allows_client_to_resume_only_missing(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    recording = client.post('/api/recordings', json={'language_type': 'english'}, headers=headers).json()
    body = b'fragment'
    client.put(f"/api/recordings/{recording['id']}/chunks/1", content=body, headers={**headers, 'X-Chunk-Sha256': hashlib.sha256(body).hexdigest(), 'Content-Type': 'video/mp4'})

    response = client.get(f"/api/recordings/{recording['id']}/chunks", headers=headers)

    assert response.status_code == 200
    assert response.json()['received_sequences'] == [1]


def test_abandon_marks_incomplete_recording(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    recording = client.post('/api/recordings', json={'language_type': 'english'}, headers=headers).json()

    response = client.post(f"/api/recordings/{recording['id']}/abandon", headers=headers)

    assert response.status_code == 200
    assert response.json()['status'] == 'abandoned'
