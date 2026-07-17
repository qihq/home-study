# DS918+ Single-Container Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export a DS918+ `linux/amd64` release that runs the API and job worker in one Container Manager container.

**Architecture:** The entrypoint runs Alembic once, starts the worker in the background, and keeps Uvicorn as the foreground process. A signal trap forwards container shutdown to both child processes. The release Compose file contains one service with `/data` storage and port `8000` only.

**Tech Stack:** POSIX shell, Python 3.12, Uvicorn, Docker Buildx, Docker Compose.

## Global Constraints

- Publish `linux/amd64` only for DS918+.
- Retain real Alembic migration before either service starts.
- Use one NAS directory mapped to `/data` and one host port mapped to container `8000`.
- Preserve the existing two-process image mode as `app` and `worker` commands for compatibility.

---

### Task 1: Single-Process-Container Entrypoint

**Files:**
- Modify: `deploy/entrypoint.sh`
- Modify: `backend/tests/test_entrypoint_migrations.py`

- [x] **Step 1: Write a failing static entrypoint test**

Assert that `single` obtains the migration lock before spawning `python -m app.workers.runner`, starts Uvicorn, records both PIDs, and traps `TERM`/`INT` to kill both.

- [x] **Step 2: Run the test to verify RED**

Run: `python -m pytest backend/tests/test_entrypoint_migrations.py -q`

Expected: FAIL because the `single` branch does not exist.

- [x] **Step 3: Add the `single` entrypoint branch**

Add a branch which runs `flock -x /data/.alembic-upgrade.lock alembic upgrade head`, backgrounds the worker and Uvicorn, then waits for both with a cleanup trap.

- [x] **Step 4: Run the targeted test to verify GREEN**

Run: `python -m pytest backend/tests/test_entrypoint_migrations.py -q`

Expected: PASS.

### Task 2: Single-Container Release Package

**Files:**
- Create: `dist/ds918plus-20260715-single/Dockerfile.release`
- Create: `dist/ds918plus-20260715-single/compose.yaml`
- Create: `dist/ds918plus-20260715-single/VERSION.md`

- [x] **Step 1: Package one-service configuration**

Set `image: family-learning:ds918plus-amd64-20260715-single`, mount `${FAMILY_LEARNING_DATA_DIR:-./data}:/data`, map `${FAMILY_LEARNING_PORT:-8000}:8000`, and omit a separate worker service.

- [x] **Step 2: Build and smoke-test the image**

Run: `docker buildx build --platform linux/amd64 --load -t family-learning:ds918plus-amd64-20260715-single -f dist/ds918plus-20260715-single/Dockerfile.release .`

Run one container on an unused host port and verify `/api/setup/status` returns HTTP 200 while both Uvicorn and worker remain alive.

- [x] **Step 3: Export and re-import the release**

Export a tar and SHA-256 file, validate `docker compose -f dist/ds918plus-20260715-single/compose.yaml config --quiet`, remove the local tag, then `docker load` the tar and inspect `linux/amd64` plus the exact tag.
