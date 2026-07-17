#!/bin/sh
set -eu

mkdir -p "${APP_DATA_DIR:-/data}"

case "${1:-app}" in
  app)
    cd /app/backend
    flock -x /data/.alembic-upgrade.lock alembic upgrade head
    cd /app
    python -m app.workers.runner &
    worker_pid=$!
    uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    api_pid=$!
    trap 'kill $worker_pid $api_pid; wait $worker_pid $api_pid' TERM INT
    trap 'kill $worker_pid $api_pid 2>/dev/null || true' EXIT
    while kill -0 "$worker_pid" 2>/dev/null && kill -0 "$api_pid" 2>/dev/null; do
      sleep 2
    done
    echo "API or worker exited; restarting container" >&2
    exit 1
    ;;
  worker)
    cd /app/backend
    flock -x /data/.alembic-upgrade.lock alembic upgrade head
    cd /app
    exec python -m app.workers.runner
    ;;
  single)
    cd /app/backend
    flock -x /data/.alembic-upgrade.lock alembic upgrade head
    cd /app
    python -m app.workers.runner &
    worker_pid=$!
    uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    api_pid=$!
    trap 'kill $worker_pid $api_pid; wait $worker_pid $api_pid' TERM INT
    trap 'kill $worker_pid $api_pid 2>/dev/null || true' EXIT
    while kill -0 "$worker_pid" 2>/dev/null && kill -0 "$api_pid" 2>/dev/null; do
      sleep 2
    done
    echo "API or worker exited; restarting container" >&2
    exit 1
    ;;
  *)
    exec "$@"
    ;;
esac
