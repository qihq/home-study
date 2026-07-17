def test_video_library_lists_recordings_with_download_readiness(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    created = client.post('/api/recordings', json={'language_type': 'english'}, headers=headers).json()

    response = client.get('/api/recordings', headers=headers)

    assert response.status_code == 200
    item = next(item for item in response.json() if item['id'] == created['id'])
    assert item['language_type'] == 'english'
    assert item['download_ready'] is False
