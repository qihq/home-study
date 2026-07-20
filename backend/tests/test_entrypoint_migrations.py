from pathlib import Path


def test_app_and_worker_upgrade_before_starting_services() -> None:
    script = (Path(__file__).parents[2] / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')

    app_branch = script.split('  app)')[1].split('  worker)')[0]
    worker_branch = script.split('  worker)')[1].split('  *)')[0]

    assert app_branch.index('alembic upgrade head') < app_branch.index('python -m app.workers.runner &')
    assert app_branch.index('alembic upgrade head') < app_branch.index('uvicorn app.main:app')
    assert worker_branch.index('alembic upgrade head') < worker_branch.index('exec python -m app.workers.runner')
    assert script.startswith('#!/bin/sh\nset -eu\n')


def test_app_and_worker_serialize_migrations_with_a_shared_exclusive_lock() -> None:
    script = (Path(__file__).parents[2] / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')

    app_branch = script.split('  app)')[1].split('  worker)')[0]
    worker_branch = script.split('  worker)')[1].split('  *)')[0]
    lock_command = 'flock -x /data/.alembic-upgrade.lock alembic upgrade head'

    assert lock_command in app_branch
    assert lock_command in worker_branch


def test_single_container_mode_runs_migration_worker_and_api_with_cleanup() -> None:
    script = (Path(__file__).parents[2] / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')

    single_branch = script.split('  single)')[1].split('  *)')[0]
    lock_command = 'flock -x /data/.alembic-upgrade.lock alembic upgrade head'

    assert single_branch.index(lock_command) < single_branch.index('python -m app.workers.runner &')
    assert single_branch.index(lock_command) < single_branch.index('uvicorn app.main:app')
    assert 'worker_pid=$!' in single_branch
    assert 'api_pid=$!' in single_branch
    assert "trap 'kill $worker_pid $api_pid; wait $worker_pid $api_pid' TERM INT" in single_branch
    assert "trap 'kill $worker_pid $api_pid 2>/dev/null || true' EXIT" in single_branch


def test_legacy_app_command_also_runs_worker_and_api() -> None:
    script = (Path(__file__).parents[2] / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')

    app_branch = script.split('  app)')[1].split('  worker)')[0]
    assert 'python -m app.workers.runner &' in app_branch
    assert 'uvicorn app.main:app --host 0.0.0.0 --port 8000 &' in app_branch
    assert 'while kill -0 "$worker_pid"' in app_branch


def test_entrypoint_creates_the_data_directory_before_locking_migrations() -> None:
    script = (Path(__file__).parents[2] / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')

    assert script.index('mkdir -p "${APP_DATA_DIR:-/data}"') < script.index('case "${1:-app}" in')


def test_all_in_one_images_start_api_and_worker_by_default() -> None:
    root = Path(__file__).parents[2]

    for dockerfile in ('Dockerfile', 'Dockerfile.release-local'):
        content = (root / 'deploy' / dockerfile).read_text(encoding='utf-8')
        assert 'CMD ["single"]' in content


def test_docker_python_installs_apply_timeout_and_retries_to_all_downloads() -> None:
    content = (Path(__file__).parents[2] / 'deploy' / 'Dockerfile').read_text(encoding='utf-8')

    assert 'ENV PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10' in content
    assert 'PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10 pip install' not in content


def test_docker_python_index_is_configurable_for_reliable_builds() -> None:
    content = (Path(__file__).parents[2] / 'deploy' / 'Dockerfile').read_text(encoding='utf-8')

    assert 'ARG PIP_INDEX_URL=' in content
    assert 'ENV PIP_INDEX_URL=${PIP_INDEX_URL}' in content
