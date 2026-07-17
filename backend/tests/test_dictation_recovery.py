def test_reveal_returns_answer_only_after_explicit_parent_action(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': '第一周', 'pasted_text': 'Apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()
    started = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id']}, headers=headers).json()
    result_id = started['results'][0]['id']

    before = client.get(f"/api/dictation-sessions/{started['id']}", headers=headers)
    revealed = client.post(f"/api/dictation-sessions/{started['id']}/results/{result_id}/reveal", headers=headers)

    assert 'display_text' not in before.json()['results'][0]
    assert revealed.json()['display_text'] == 'Apple'


def test_complete_session_rejects_unscored_results(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': '第一周', 'pasted_text': 'Apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()
    started = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id']}, headers=headers).json()

    response = client.post(f"/api/dictation-sessions/{started['id']}/complete", headers=headers)

    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'DICTATION_HAS_UNSCORED_RESULTS'


def test_session_recovery_includes_audio_asset_state(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    word_list = client.post('/api/word-lists', json={'title': '第一周', 'pasted_text': 'Apple'}, headers=headers).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()
    started = client.post('/api/dictation-sessions', json={'word_list_version_id': version['word_list_version_id']}, headers=headers).json()

    recovered = client.get(f"/api/dictation-sessions/{started['id']}", headers=headers)

    assert 'audio_asset_id' in recovered.json()['results'][0]
