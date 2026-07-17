import hashlib

from fastapi.testclient import TestClient


def auth_cookie(client: TestClient) -> dict[str, str]:
    response = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    return {'Cookie': response.headers['set-cookie'].split(';', 1)[0]}


def create_recording(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post('/api/recordings', json={'language_type': 'chinese'}, headers=headers)
    assert response.status_code == 201
    return response.json()['id']


def test_repeated_chunk_with_same_hash_is_idempotent(client: TestClient, admin_user) -> None:
    headers = auth_cookie(client)
    recording_id = create_recording(client, headers)
    body = b'video-fragment'
    chunk_headers = {
        **headers,
        'X-Chunk-Sha256': hashlib.sha256(body).hexdigest(),
        'Content-Type': 'video/mp4',
    }

    first = client.put(f'/api/recordings/{recording_id}/chunks/0', content=body, headers=chunk_headers)
    second = client.put(f'/api/recordings/{recording_id}/chunks/0', content=body, headers=chunk_headers)

    assert first.status_code == second.status_code == 200
    assert second.json()['idempotent'] is True


def test_complete_reports_missing_sequences(client: TestClient, admin_user) -> None:
    headers = auth_cookie(client)
    recording_id = create_recording(client, headers)

    response = client.post(f'/api/recordings/{recording_id}/complete', json={'final_chunk_count': 2}, headers=headers)

    assert response.status_code == 200
    assert response.json()['missing_sequences'] == [0, 1]


def test_complete_enqueues_one_assembly_job_when_chunks_are_complete(client: TestClient, admin_user) -> None:
    headers = auth_cookie(client)
    recording_id = create_recording(client, headers)
    body = b'complete-fragment'
    response = client.put(
        f'/api/recordings/{recording_id}/chunks/0', content=body,
        headers={**headers, 'X-Chunk-Sha256': hashlib.sha256(body).hexdigest(), 'Content-Type': 'video/mp4'},
    )
    assert response.status_code == 200

    first = client.post(f'/api/recordings/{recording_id}/complete', json={'final_chunk_count': 1}, headers=headers)
    second = client.post(f'/api/recordings/{recording_id}/complete', json={'final_chunk_count': 1}, headers=headers)

    assert first.json()['status'] == 'assembling'
    assert second.json()['status'] == 'assembling'
    from app.db.session import get_session_factory
    from app.models.job import Job
    with get_session_factory()() as session:
        assert len(session.query(Job).filter_by(type='assemble_video', entity_id=recording_id).all()) == 1
