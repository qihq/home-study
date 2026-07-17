from pathlib import Path


def test_application_serves_built_frontend_when_present(tmp_path: Path, monkeypatch) -> None:
    frontend = tmp_path / 'frontend-dist'
    frontend.mkdir()
    (frontend / 'index.html').write_text('<div>家庭学习助手</div>', encoding='utf-8')
    monkeypatch.setenv('APP_FRONTEND_DIR', str(frontend))

    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    response = TestClient(create_app()).get('/')

    assert response.status_code == 200
    assert '家庭学习助手' in response.text


def test_application_serves_service_worker_as_javascript(tmp_path: Path, monkeypatch) -> None:
    frontend = tmp_path / 'frontend-dist'
    frontend.mkdir()
    (frontend / 'index.html').write_text('<div>家庭学习助手</div>', encoding='utf-8')
    (frontend / 'service-worker.js').write_text('self.addEventListener("install", () => {});', encoding='utf-8')
    monkeypatch.setenv('APP_FRONTEND_DIR', str(frontend))

    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    response = TestClient(create_app()).get('/service-worker.js')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/javascript')
    assert 'self.addEventListener' in response.text
