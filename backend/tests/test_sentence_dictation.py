from fastapi.testclient import TestClient


def _authenticated_headers(client: TestClient) -> dict[str, str]:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    return {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}


def test_sentence_answer_is_hidden_until_reveal_and_requires_manual_scoring(client: TestClient, admin_user) -> None:
    headers = _authenticated_headers(client)
    word_list = client.post(
        '/api/word-lists', json={'title': 'Sentence week', 'pasted_text': 'I like apples.'}, headers=headers
    ).json()
    version = client.post(f"/api/word-lists/{word_list['id']}/confirm", headers=headers).json()

    started = client.post(
        '/api/dictation-sessions',
        json={'word_list_version_id': version['word_list_version_id'], 'mode': 'ordered'},
        headers=headers,
    ).json()

    assert 'I like apples.' not in str(started)
    result_id = started['results'][0]['id']
    revealed = client.post(
        f"/api/dictation-sessions/{started['id']}/results/{result_id}/reveal", headers=headers
    ).json()
    assert revealed['answer'] == 'I like apples.'

    scored = client.patch(
        f"/api/dictation-sessions/{started['id']}/results/{result_id}",
        json={'result': 'correct'}, headers=headers,
    ).json()
    assert scored == {'id': result_id, 'result': 'correct'}

    recovered = client.get(f"/api/dictation-sessions/{started['id']}", headers=headers).json()
    assert recovered['results'][0]['item_type'] == 'sentence'
