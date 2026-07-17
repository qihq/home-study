def test_ai_key_is_separate_from_tts_and_never_returned(client, admin_user) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    saved = client.patch('/api/settings/ai', json={
        'protocol': 'openai_chat_compatible',
        'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1',
        'api_key': 'ai-secret-abcd',
        'model': 'custom-model',
        'temperature': 0.1,
        'timeout_seconds': 45,
        'enabled': True,
    }, headers=headers)

    assert saved.status_code == 200
    assert 'ai-secret-abcd' not in saved.text
    response = client.get('/api/settings/ai', headers=headers)
    assert 'ai-secret-abcd' not in response.text
    assert response.json() == {
        'protocol': 'openai_chat_compatible',
        'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1',
        'model': 'custom-model',
        'temperature': 0.1,
        'timeout_seconds': 45,
        'enabled': True,
        'api_key_configured': True,
        'api_key_mask': '********abcd',
    }
    assert client.get('/api/settings/tts', headers=headers).json()['api_key_configured'] is False


def test_ai_connection_test_returns_stable_success_shape(client, admin_user, monkeypatch) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    client.patch('/api/settings/ai', json={
        'protocol': 'openai_chat_compatible', 'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1', 'api_key': 'ai-secret-abcd',
        'model': 'custom-model', 'temperature': 0.1, 'timeout_seconds': 45, 'enabled': True,
    }, headers=headers)
    monkeypatch.setattr('app.services.openai_chat.OpenAiChatClient.complete', lambda *_args: '{"ok": true}')

    response = client.post('/api/settings/ai/test', headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body['ok'] is True
    assert body['display_name'] == 'OpenCode Go'
    assert body['model'] == 'custom-model'
    assert isinstance(body['latency_ms'], int)


def test_ai_connection_test_returns_stable_upstream_error(client, admin_user, monkeypatch) -> None:
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}
    client.patch('/api/settings/ai', json={
        'protocol': 'openai_chat_compatible', 'display_name': 'OpenCode Go',
        'base_url': 'https://provider.example/v1', 'api_key': 'ai-secret-abcd',
        'model': 'custom-model', 'temperature': 0.1, 'timeout_seconds': 45, 'enabled': True,
    }, headers=headers)
    monkeypatch.setattr(
        'app.services.openai_chat.OpenAiChatClient.complete',
        lambda *_args: (_ for _ in ()).throw(__import__('app.services.openai_chat', fromlist=['OpenAiChatError']).OpenAiChatError('AI_AUTH_FAILED')),
    )

    response = client.post('/api/settings/ai/test', headers=headers)

    assert response.status_code == 502
    assert response.json() == {'detail': {'code': 'AI_AUTH_FAILED', 'message': 'AI 服务认证失败'}}
    assert 'ai-secret-abcd' not in response.text
