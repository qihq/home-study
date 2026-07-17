def test_backup_endpoint_requires_login_and_returns_backup_name(client, admin_user) -> None:
    assert client.post('/api/settings/backup').status_code == 401
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.post('/api/settings/backup', headers=headers)

    assert response.status_code == 201
    assert response.json()['filename'].endswith('.zip')


def test_settings_list_and_retry_failed_voice_jobs(client, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.job import Job

    with get_session_factory()() as session:
        failed = Job(type='voice_preview', entity_id='voice-1', status='failed', error_code='VOICE_CLONE_FAILED')
        ignored = Job(type='assemble_video', entity_id='video-1', status='failed', error_code='VIDEO_FAILED')
        session.add_all([failed, ignored])
        session.commit()
        failed_id = failed.id
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    listed = client.get('/api/settings/failed-tasks', headers=headers)
    retried = client.post(f'/api/settings/failed-tasks/{failed_id}/retry', headers=headers)

    assert listed.json() == [{'id': failed_id, 'type': 'voice_preview', 'entity_id': 'voice-1', 'error_code': 'VOICE_CLONE_FAILED'}]
    assert retried.json() == {'id': failed_id, 'status': 'queued'}
    with get_session_factory()() as session:
        job = session.get(Job, failed_id)
        assert job.status == 'queued'
        assert job.error_code is None


def test_settings_only_lists_and_retries_worker_supported_voice_jobs(client, admin_user) -> None:
    from app.db.session import get_session_factory
    from app.models.job import Job

    with get_session_factory()() as session:
        supported = Job(type='normalize_voice_sample', entity_id='voice-1', status='failed')
        unsupported_ai = Job(type='ai_lookup', entity_id='lookup-1', status='failed')
        unsupported_dictionary = Job(type='dictionary_lookup', entity_id='lookup-2', status='failed')
        session.add_all([supported, unsupported_ai, unsupported_dictionary])
        session.commit()
        unsupported_ids = [unsupported_ai.id, unsupported_dictionary.id]
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    listed = client.get('/api/settings/failed-tasks', headers=headers)

    assert [task['type'] for task in listed.json()] == ['normalize_voice_sample']
    for unsupported_id in unsupported_ids:
        retried = client.post(f'/api/settings/failed-tasks/{unsupported_id}/retry', headers=headers)
        assert retried.status_code == 404
