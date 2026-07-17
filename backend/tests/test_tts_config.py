def test_tts_health_reports_unconfigured_without_exposing_key(client, admin_user, monkeypatch) -> None:
    monkeypatch.delenv('APP_MIMO_API_KEY', raising=False)
    from app.core.config import get_settings
    get_settings.cache_clear()
    login = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    headers = {'Cookie': login.headers['set-cookie'].split(';', 1)[0]}

    response = client.get('/api/settings/tts/status', headers=headers)

    assert response.status_code == 200
    assert response.json() == {'configured': False, 'provider': 'mimo'}
    assert 'key' not in response.text.casefold()
