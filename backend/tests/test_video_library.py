from pathlib import Path


def test_parent_can_upload_a_video_for_a_selected_reading_date(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.post(
        '/api/recordings/upload', headers=headers,
        data={'reading_date': '2026-07-18', 'language_type': 'english'},
        files={'file': ('mom-video.mp4', b'video-content', 'video/mp4')},
    )

    assert response.status_code == 201
    assert response.json()['reading_date'] == '2026-07-18'
    assert response.json()['status'] == 'assembling'
    listed = client.get('/api/recordings', headers=headers).json()
    item = next(item for item in listed if item['id'] == response.json()['id'])
    assert item['reading_date'] == '2026-07-18'
    from app.db.session import get_session_factory
    from app.models.recording import RecordingChunk
    with get_session_factory()() as session:
        chunk = session.query(RecordingChunk).filter_by(recording_id=item['id']).one()
        assert Path(chunk.path).read_bytes() == b'video-content'


def test_video_library_lists_recordings_with_download_readiness(client, admin_user):
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    created = client.post('/api/recordings', json={'language_type': 'english'}, headers=headers).json()

    response = client.get('/api/recordings', headers=headers)

    assert response.status_code == 200
    item = next(item for item in response.json() if item['id'] == created['id'])
    assert item['language_type'] == 'english'
    assert item['download_ready'] is False
