# 家庭学习助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 DS918+ 上交付可部署的家庭学习 PWA，支持 iPhone/iPad 分片阅读录制、720p 视频、单词默写和学习统计。

**Architecture:** React/Vite PWA 通过 FastAPI REST API 工作；FastAPI 和 worker 共享 SQLite 与 `/data` 卷。worker 从带租约的 SQLite 任务表领取视频组装、转码、导入解析和 TTS 任务，所有最终媒体通过临时文件校验后原子落盘。

**Tech Stack:** React 19、TypeScript、Vite、Vitest、FastAPI、SQLAlchemy 2、Alembic、Pydantic Settings、SQLite、pytest、FFmpeg、Docker Compose。

## Global Constraints

- 生产入口必须位于 HTTPS 反向代理之后；不要在应用内配置公网、DNS 或证书。
- 源视频、720p 视频、导入原件和 TTS 缓存默认永久保留；应用不自动删除已验证源视频。
- 阅读完成以 `source_validated_at` 非空且 `source_missing_at` 为空的正式视频为准，不依赖转码成功。
- iOS 网页只允许用户通过分享菜单手动保存 720p 视频；不得宣称静默写入相册。
- API Key 只能存在于后端配置，前端、普通 API 响应和日志不得泄露它。
- 所有业务代码以测试先行：先看到失败测试，再加入最小实现，最后运行完整测试集。
- 第一版一个管理员和一个默认孩子档案，表结构仍以 `child_id` 关联资源。
- UI 必须一套代码适配 iPhone（小于 768px）、iPad（768px 至 1199px）和桌面（1200px 及以上）；录制优先移动 Safari，管理/视频库/统计必须在三端可访问。
- 视频转码并发为 1、OCR 为 1、TTS 为 2；worker 任务必须幂等。

---

## File Structure

```text
family-learning/
  backend/
    app/
      api/                 # FastAPI 路由和依赖项
      core/                # 配置、认证、错误、路径与时间
      db/                  # engine、会话和 Alembic 元数据
      models/              # SQLAlchemy 表模型
      schemas/             # Pydantic 请求/响应模型
      services/            # 业务规则，不直接处理 HTTP
      workers/             # 任务领取和处理器
      main.py
    alembic/
    tests/
  frontend/
    src/
      api/                 # typed fetch client
      features/            # dashboard、recording、word-list、dictation、stats
      lib/                 # IndexedDB、日期、PWA helpers
      ui/                  # button、dialog、layout 等共享组件
    tests/
  deploy/
    Dockerfile
    compose.yaml
    entrypoint.sh
  docs/
    DEPLOYMENT.md
    IOS-TEST-CHECKLIST.md
  .env.example
  README.md
```

## Task 1: 创建仓库骨架、Compose 和可运行健康检查

**Files:**
- Create: `package.json`, `frontend/package.json`, `backend/pyproject.toml`
- Create: `deploy/Dockerfile`, `deploy/compose.yaml`, `deploy/entrypoint.sh`, `.env.example`
- Create: `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/health.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces `GET /api/health` returning `{ "status": "ok", "database": true, "media": true, "ffmpeg": true, "vaapi": boolean }`.
- Produces `docker compose -f deploy/compose.yaml up` with `app` and `worker` services sharing `/data`.

- [ ] **Step 1: Write the failing health test**

```python
def test_health_reports_database_media_and_ffmpeg(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['database'] is True
    assert response.json()['media'] is True
    assert isinstance(response.json()['vaapi'], bool)
```

- [ ] **Step 2: Run it and observe import failure**

Run: `cd backend && pytest tests/test_health.py -q`

Expected: FAIL because `app.main` and the test application do not exist.

- [ ] **Step 3: Add minimal FastAPI application and configuration**

```python
# backend/app/main.py
from fastapi import FastAPI
from app.api.health import router as health_router

def create_app() -> FastAPI:
    app = FastAPI(title='Family Learning API', version='0.1.0')
    app.include_router(health_router, prefix='/api')
    return app

app = create_app()
```

`config.py` must create `data_dir`, `uploads_dir`, `videos_dir`, `tts_dir`, `backups_dir`; `health.py` must test writable media storage and invoke `ffmpeg -version` without logging command output on failure.

- [ ] **Step 4: Run the focused test**

Run: `cd backend && pytest tests/test_health.py -q`

Expected: PASS.

- [ ] **Step 5: Add deployment files and verify Compose syntax**

`deploy/compose.yaml` must mount one host data directory at `/data`, set `APP_DATA_DIR=/data`, expose only app port `8000` to its Docker network, and give worker no host port. The Dockerfile must install `ffmpeg` and define `app` / `worker` entry commands.

Run: `docker compose -f deploy/compose.yaml config`

Expected: valid resolved Compose configuration.

## Task 2: 数据库迁移、默认孩子和带租约任务队列

**Files:**
- Create: `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/alembic.ini`, `backend/alembic/env.py`
- Create: `backend/app/models/{child,job,recording,word_list,dictation,tts_asset}.py`
- Create: `backend/app/services/jobs.py`, `backend/app/services/bootstrap.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/test_jobs.py`, `backend/tests/test_bootstrap.py`

**Interfaces:**
- Produces `claim_next_job(session, worker_id, now) -> Job | None`.
- Produces `bootstrap_default_child(session, display_name, timezone) -> Child`.
- All IDs are UUID strings; SQLite uses WAL and foreign keys.

- [ ] **Step 1: Write failing queue and bootstrap tests**

```python
def test_claim_reclaims_expired_lease(session, frozen_now):
    job = create_job(session, type='transcode_video', entity_id='r1')
    job.status, job.locked_at = 'running', frozen_now - timedelta(minutes=6)
    claimed = claim_next_job(session, 'worker-a', frozen_now)
    assert claimed.id == job.id
    assert claimed.locked_by == 'worker-a'

def test_bootstrap_creates_only_one_default_child(session):
    first = bootstrap_default_child(session, '孩子', 'Asia/Shanghai')
    second = bootstrap_default_child(session, '孩子', 'Asia/Shanghai')
    assert first.id == second.id
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd backend && pytest tests/test_jobs.py tests/test_bootstrap.py -q`

Expected: FAIL because models and service functions do not exist.

- [ ] **Step 3: Implement migrations and queue operations**

Create the schema defined in the design: children, recordings, recording_chunks, word_lists, word_list_versions, word_items, tts_assets, dictation_sessions, dictation_results, jobs and audit_events. Add the partial unique index ensuring only one official video per child/date/language.

`claim_next_job` must atomically claim the oldest queued due job or expired running job and set `locked_at`, `locked_by`, `status='running'`, and increment `attempts`.

- [ ] **Step 4: Run focused database tests**

Run: `cd backend && pytest tests/test_jobs.py tests/test_bootstrap.py -q`

Expected: PASS.

- [ ] **Step 5: Run migration smoke test**

Run: `cd backend && alembic upgrade head && pytest -q`

Expected: migration succeeds and all backend tests pass.

## Task 3: 管理员认证、会话和安全边界

**Files:**
- Create: `backend/app/models/user.py`, `backend/app/core/security.py`, `backend/app/api/deps.py`
- Create: `backend/app/api/auth.py`, `backend/app/schemas/auth.py`, `backend/app/services/users.py`
- Modify: `backend/alembic/versions/0001_initial.py`, `backend/app/main.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Produces `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/me`.
- Produces `require_user` FastAPI dependency returning `User` or HTTP 401.

- [ ] **Step 1: Write failing authentication tests**

```python
def test_login_sets_secure_http_only_session_cookie(client, admin_user):
    response = client.post('/api/auth/login', json={'username': 'parent', 'password': 'correct horse'})
    assert response.status_code == 200
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie

def test_private_route_rejects_anonymous_user(client):
    assert client.get('/api/me').status_code == 401
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_auth.py -q`

Expected: FAIL because login and session dependencies do not exist.

- [ ] **Step 3: Implement Argon2id password verification and signed server sessions**

Use `pwdlib[argon2]` for hashes. Store a random session token hash in SQLite, set cookie flags from settings (`Secure` true in production), and rotate the cookie on successful login. API errors must use `{ "code": "AUTH_REQUIRED", "message": "..." }` shape.

- [ ] **Step 4: Run focused and full backend tests**

Run: `cd backend && pytest tests/test_auth.py -q && pytest -q`

Expected: all pass.

## Task 4: 阅读录制会话与幂等分片上传 API

**Files:**
- Create: `backend/app/api/recordings.py`, `backend/app/schemas/recordings.py`
- Create: `backend/app/services/recordings.py`, `backend/app/core/files.py`
- Modify: `backend/app/main.py`, `backend/app/models/recording.py`
- Test: `backend/tests/test_recordings.py`

**Interfaces:**
- Produces `POST /api/recordings`, `PUT /api/recordings/{id}/chunks/{sequence}`, `GET /api/recordings/{id}/chunks`, `POST /api/recordings/{id}/complete`, `POST /api/recordings/{id}/abandon`.
- `upload_chunk(recording_id, sequence, stream, sha256, mime_type) -> ChunkReceipt` is idempotent.

- [ ] **Step 1: Write failing upload tests**

```python
def test_repeated_chunk_with_same_hash_is_idempotent(client, auth_headers):
    recording_id = create_recording(client, auth_headers)
    body = b'video-fragment'
    headers = {'X-Chunk-Sha256': hashlib.sha256(body).hexdigest(), 'Content-Type': 'video/mp4'}
    first = client.put(f'/api/recordings/{recording_id}/chunks/0', content=body, headers=headers)
    second = client.put(f'/api/recordings/{recording_id}/chunks/0', content=body, headers=headers)
    assert first.status_code == second.status_code == 200

def test_complete_reports_missing_sequences(client, auth_headers):
    recording_id = create_recording(client, auth_headers)
    response = client.post(f'/api/recordings/{recording_id}/complete', json={'final_chunk_count': 2})
    assert response.json()['missing_sequences'] == [0, 1]
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_recordings.py -q`

Expected: FAIL because recording routes and services do not exist.

- [ ] **Step 3: Implement safe chunk persistence**

Create unpredictable UUID recording IDs; only accept `chinese` and `english`; stream each chunk to `<sequence>.part`, verify exact SHA-256, atomically rename to `<sequence>.bin`, then insert the row. Same sequence/different hash must return 409 `CHUNK_HASH_MISMATCH`. Complete must return a sorted missing sequence list or enqueue one `assemble_video` job exactly once.

- [ ] **Step 4: Run focused tests**

Run: `cd backend && pytest tests/test_recordings.py -q`

Expected: PASS.

## Task 5: 视频组装、源文件验证、720p 转码和下载

**Files:**
- Create: `backend/app/workers/runner.py`, `backend/app/workers/video.py`, `backend/app/services/media.py`
- Modify: `backend/app/api/recordings.py`, `backend/app/services/recordings.py`
- Test: `backend/tests/test_video_worker.py`, `backend/tests/test_recording_download.py`

**Interfaces:**
- Produces `process_assemble_video(job)`, `process_transcode_video(job)`.
- Produces `GET /api/recordings/{id}/download/720p` only for ready compressed asset and authenticated user.

- [ ] **Step 1: Write failing worker tests using generated FFmpeg fixtures**

```python
def test_verified_source_makes_first_recording_official(session, video_fixture):
    recording = recording_with_complete_chunks(session, video_fixture)
    process_assemble_video(job_for(recording))
    session.refresh(recording)
    assert recording.source_validated_at is not None
    assert recording.is_official is True

def test_transcode_failure_keeps_source_completion(session, video_fixture, mocker):
    recording = assembled_recording(session, video_fixture)
    mocker.patch('app.workers.video.run_ffmpeg', side_effect=MediaError('encoder failed'))
    process_transcode_video(job_for(recording))
    assert recording.source_validated_at is not None
    assert recording.status == 'transcode_failed'
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_video_worker.py -q`

Expected: FAIL because worker functions are absent.

- [ ] **Step 3: Implement media pipeline**

Use one actual fixture generated locally with FFmpeg. Assemble only contiguous chunks; for supported fMP4 concatenate/remux with FFmpeg and write `source.part`. Validate with ffprobe that one video and one audio stream exist and duration is positive, then atomically promote source and set `source_validated_at`. Enqueue one transcode job.

Transcode with VAAPI only when the startup check reports it available; otherwise use `libx264`, `-vf scale=w=1280:h=720:force_original_aspect_ratio=decrease`, AAC 128k, max 30 fps, `yuv420p`, `+faststart`. Validate final file using ffprobe and three decode seek checks before promotion.

- [ ] **Step 4: Run focused media tests**

Run: `cd backend && pytest tests/test_video_worker.py tests/test_recording_download.py -q`

Expected: PASS.

## Task 6: 阅读统计和视频库 API

**Files:**
- Create: `backend/app/services/reading_stats.py`, `backend/app/api/stats.py`
- Modify: `backend/app/api/recordings.py`, `backend/app/schemas/recordings.py`
- Test: `backend/tests/test_reading_stats.py`, `backend/tests/test_official_recording.py`

**Interfaces:**
- Produces `GET /api/stats/reading?period=month&date=YYYY-MM-DD`.
- Produces `POST /api/recordings/{id}/make-official`.

- [ ] **Step 1: Write failing statistics tests**

```python
def test_current_month_excludes_future_days(session):
    stats = build_reading_stats(session, child_id='c1', period='month', today=date(2026, 7, 12))
    assert stats.available_days == 12

def test_transcode_failure_still_counts_completed_source(session):
    create_official_recording(session, 'chinese', source_validated=True, status='transcode_failed')
    stats = build_reading_stats(session, child_id='c1', period='week', today=date(2026, 7, 12))
    assert stats.chinese.completed_days == 1
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_reading_stats.py tests/test_official_recording.py -q`

Expected: FAIL because stats service is absent.

- [ ] **Step 3: Implement stat calculations and official switch transaction**

Use child timezone and inclusive current date. A completed language requires `source_validated_at IS NOT NULL`, `source_missing_at IS NULL`, and `is_official`. Switch official video in one transaction, then return calendar items, language totals, combined rate, current dual-language streak and longest historical streak.

- [ ] **Step 4: Run backend suite**

Run: `cd backend && pytest -q`

Expected: PASS.

## Task 7: 单词导入、确认版本和安全文件解析

**Files:**
- Create: `backend/app/api/imports.py`, `backend/app/api/word_lists.py`
- Create: `backend/app/services/imports.py`, `backend/app/services/words.py`
- Create: `backend/app/workers/imports.py`
- Test: `backend/tests/test_imports.py`, `backend/tests/test_words.py`

**Interfaces:**
- Produces `POST /api/imports`, `GET /api/imports/{id}`, `GET/POST/PATCH /api/word-lists`, `POST /api/word-lists/{id}/confirm`.
- Produces `normalize_word(text) -> str` and a versioned confirmed list.

- [ ] **Step 1: Write failing parsing and confirmation tests**

```python
def test_pasted_text_preserves_display_text_but_normalizes_for_dedupe():
    items = parse_pasted_words('  Apple\napple\nice-to-meet you ')
    assert [item.display_text for item in items] == ['Apple', 'nice-to-meet you']
    assert [item.normalized_text for item in items] == ['apple', 'nice-to-meet you']

def test_confirming_list_creates_immutable_version(session):
    word_list = create_draft_list(session, ['colour'])
    version = confirm_word_list(session, word_list.id)
    assert version.version == 1
    assert word_list.status == 'confirmed'
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_imports.py tests/test_words.py -q`

Expected: FAIL because import services are absent.

- [ ] **Step 3: Implement supported parsers and guarded upload storage**

Accept plain text, JPG/PNG/HEIC images, XLSX, DOCX, and PDF. Enforce configured file-size/page limits, use generated storage names, and preserve source locations. Use native text extraction first for PDF and OCR only when text is absent. Mark any uncertainty as warnings. Do not call external AI during parsing.

- [ ] **Step 4: Run focused tests**

Run: `cd backend && pytest tests/test_imports.py tests/test_words.py -q`

Expected: PASS.

## Task 8: MiMo TTS 适配器、缓存和默写会话

**Files:**
- Create: `backend/app/services/tts.py`, `backend/app/workers/tts.py`
- Create: `backend/app/api/dictation.py`, `backend/app/services/dictation.py`
- Test: `backend/tests/test_tts.py`, `backend/tests/test_dictation.py`

**Interfaces:**
- Produces `synthesize(text, locale, voice, speed, output_format) -> TtsResult` adapter protocol.
- Produces `POST /api/dictation-sessions`, `GET /api/dictation-sessions/{id}`, `PATCH /api/dictation-sessions/{id}/results/{result_id}`, `POST /api/dictation-sessions/{id}/complete`.

- [ ] **Step 1: Write failing cache and order tests**

```python
def test_same_tts_request_reuses_cached_asset(session, fake_tts):
    first = ensure_tts_asset(session, fake_tts, text='apple', locale='en-US', voice='amy', speed=1.0)
    second = ensure_tts_asset(session, fake_tts, text='apple', locale='en-US', voice='amy', speed=1.0)
    assert first.id == second.id
    assert fake_tts.calls == 1

def test_random_session_order_is_persisted(session):
    session_record = start_dictation(session, word_list_version_id='v1', mode='random', random_source=random.Random(2))
    assert session_record.ordered_item_ids_json == start_dictation_order(session_record)
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_tts.py tests/test_dictation.py -q`

Expected: FAIL because TTS and dictation services do not exist.

- [ ] **Step 3: Implement adapter, cache and manual scoring**

Make MiMo endpoint, model, voice, speed and API key configurable from server settings. Hash normalized JSON cache settings with SHA-256. A TTS job writes audio via a temporary path, normalizes to MP3, records failure class, and never exposes secret configuration. Dictation creates all `unscored` result rows, persists fixed ordered/random item IDs, increments `play_count`, exposes answer only after request, and accepts only correct/incorrect/unscored results.

- [ ] **Step 4: Run focused tests**

Run: `cd backend && pytest tests/test_tts.py tests/test_dictation.py -q`

Expected: PASS.

## Task 9: 默写统计、错词复习、设置与备份 API

**Files:**
- Create: `backend/app/services/dictation_stats.py`, `backend/app/api/settings.py`, `backend/app/services/backups.py`
- Modify: `backend/app/api/stats.py`, `backend/app/api/dictation.py`
- Test: `backend/tests/test_dictation_stats.py`, `backend/tests/test_settings.py`

**Interfaces:**
- Produces `GET /api/stats/dictation`, `GET /api/stats/mistakes`, `POST /api/review-lists/from-mistakes`, `GET/PATCH /api/settings`, `POST /api/settings/tts/test`.

- [ ] **Step 1: Write failing aggregation and settings secrecy tests**

```python
def test_dictation_trend_aggregates_items_not_session_percentages(session):
    add_results(session, correct=9, incorrect=1, scored_at='2026-07-01')
    add_results(session, correct=0, incorrect=1, scored_at='2026-07-01')
    assert build_dictation_stats(session).daily[0].accuracy == 9 / 11

def test_settings_masks_api_key(client, auth_headers):
    client.patch('/api/settings', headers=auth_headers, json={'mimo_api_key': 'secret-key'})
    assert 'secret-key' not in client.get('/api/settings', headers=auth_headers).text
```

- [ ] **Step 2: Run and observe failure**

Run: `cd backend && pytest tests/test_dictation_stats.py tests/test_settings.py -q`

Expected: FAIL because aggregation and settings routes are absent.

- [ ] **Step 3: Implement statistics, review list creation and SQLite online backup**

Aggregate only scored result rows by score date; mistakes group by normalized text with last result. Creating a review list must create a new draft list and not mutate historical versions. Store API keys encrypted at rest with a server-only master key and always return masked values. Backup uses SQLite backup API to a dated file under `/data/backups`.

- [ ] **Step 4: Run full backend tests**

Run: `cd backend && pytest -q`

Expected: PASS.

## Task 10: React PWA shell、认证和首页

**Files:**
- Create: `frontend/src/{main,App}.tsx`, `frontend/src/styles.css`, `frontend/vite.config.ts`
- Create: `frontend/src/api/client.ts`, `frontend/src/features/auth/LoginPage.tsx`, `frontend/src/features/dashboard/DashboardPage.tsx`
- Create: `frontend/src/ui/{Button,AppShell,StatusCard}.tsx`
- Test: `frontend/src/features/auth/LoginPage.test.tsx`, `frontend/src/features/dashboard/DashboardPage.test.tsx`

**Interfaces:**
- Produces responsive shell with login, today Chinese/English state, weekly overview, recovery/failed-job notices and navigation.
- API client uses `credentials: 'include'` and typed error codes.

- [ ] **Step 1: Write failing component tests**

```tsx
it('renders today reading actions when both tasks are incomplete', async () => {
  render(<DashboardPage summary={incompleteSummary} />)
  expect(screen.getByRole('button', { name: '开始中文阅读' })).toBeVisible()
  expect(screen.getByRole('button', { name: '开始英文阅读' })).toBeVisible()
})
```

- [ ] **Step 2: Run and observe failure**

Run: `cd frontend && npm test -- LoginPage.test.tsx DashboardPage.test.tsx`

Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement shell with a mobile-first design system**

Use true white background, dark readable text, restrained blue/green completion colors, 44px minimum touch targets, safe-area padding, and no external analytics. Implement the shared responsive shell: iPhone below 768px gets a single column and bottom navigation; iPad from 768px to 1199px gets a collapsible sidebar or two-column task layout; desktop at 1200px and above gets persistent navigation and wider library/statistics management layouts. Avoid loading all feature routes eagerly: route-level code split recording, word lists, dictation and statistics. The service worker must cache only application static assets and never API/media routes.

- [ ] **Step 4: Run component tests and production build**

Run: `cd frontend && npm test -- LoginPage.test.tsx DashboardPage.test.tsx && npm run build`

Expected: tests and Vite build pass.

## Task 11: 前端录制、IndexedDB 续传、视频库和阅读统计

**Files:**
- Create: `frontend/src/lib/{recordingStore,mediaRecorder}.ts`
- Create: `frontend/src/features/recording/{RecordingPage,UploadRecovery,VideoLibrary}.tsx`
- Create: `frontend/src/features/stats/ReadingStatsPage.tsx`
- Test: `frontend/src/lib/recordingStore.test.ts`, `frontend/src/features/recording/RecordingPage.test.tsx`

**Interfaces:**
- Produces client `RecordingStore` that persists unacknowledged blobs by recording ID/sequence.
- Produces recording page with start/stop, stream preview, 4-second chunk collection, network state and recovery.

- [ ] **Step 1: Write failing IndexedDB acknowledgement test**

```ts
it('removes a blob only after matching server acknowledgement', async () => {
  const store = createRecordingStore(fakeIndexedDb)
  await store.put('r1', 0, new Blob(['chunk']))
  await store.acknowledge('r1', 0)
  await expect(store.get('r1', 0)).resolves.toBeUndefined()
})
```

- [ ] **Step 2: Run and observe failure**

Run: `cd frontend && npm test -- recordingStore.test.ts RecordingPage.test.tsx`

Expected: FAIL because recording store and page do not exist.

- [ ] **Step 3: Implement recording and recovery without storing full video in memory**

Select a supported `MediaRecorder` MIME at runtime, request camera/microphone, write each 4-second Blob to IndexedDB before upload, SHA-256 it with `crypto.subtle`, and delete only after successful server receipt. On startup query received sequences and retry only local missing blobs. Show cache size and enforce configurable 150/250 MB warning/stop thresholds. Persist end state before calling complete. Handle `pagehide`, track end and permission errors by creating recovery state. Validate the recording layout at iPhone width, iPad portrait/landscape widths and desktop width; mobile controls stay reachable above the safe-area, iPad preview/status can be side-by-side, and desktop shows a compatibility hint without hiding the recording flow.

- [ ] **Step 4: Run focused tests and build**

Run: `cd frontend && npm test -- recordingStore.test.ts RecordingPage.test.tsx && npm run build`

Expected: tests and build pass.

## Task 12: 前端单词导入、默写、统计、管理与文档验收

**Files:**
- Create: `frontend/src/features/words/{ImportPage,WordListEditor}.tsx`
- Create: `frontend/src/features/dictation/DictationPage.tsx`
- Create: `frontend/src/features/stats/{DictationStatsPage,MistakesPage}.tsx`
- Create: `frontend/src/features/settings/SettingsPage.tsx`
- Create: `README.md`, `docs/DEPLOYMENT.md`, `docs/IOS-TEST-CHECKLIST.md`
- Test: `frontend/src/features/dictation/DictationPage.test.tsx`, `frontend/src/features/words/WordListEditor.test.tsx`

**Interfaces:**
- Produces every confirmed user path: import/confirm words, manual play/replay/next/reveal/score, review mistakes, settings test, deployment and true-device checklists.

- [ ] **Step 1: Write failing manual dictation test**

```tsx
it('hides spelling until parent reveals the answer and then records an incorrect score', async () => {
  const user = userEvent.setup()
  render(<DictationPage session={sessionWithApple} />)
  expect(screen.queryByText('apple')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '显示答案' }))
  await user.click(screen.getByRole('button', { name: '错误' }))
  expect(saveResult).toHaveBeenCalledWith(expect.objectContaining({ result: 'incorrect' }))
})
```

- [ ] **Step 2: Run and observe failure**

Run: `cd frontend && npm test -- DictationPage.test.tsx WordListEditor.test.tsx`

Expected: FAIL because these feature components do not exist.

- [ ] **Step 3: Implement feature pages and operational docs**

Import supports paste/file/camera file selection; confirmation is editable and AI suggestions are visually non-authoritative. Dictation never auto-advances or exposes spelling until reveal. Settings only display API-key masks. Verify every completed feature at iPhone, iPad portrait, iPad landscape and desktop widths; desktop may use tables and sidebars while iPhone preserves all actions in a single-column flow. Deployment documentation must state DS918+ volume mapping, `/dev/dri` option, HTTPS proxy request-size/timeout values, backup policy, first-admin provisioning, and iOS save-to-Photos steps. The checklist must include 15-minute, offline recovery, page-reopen, PWA/Safari iPhone/iPad and desktop browser verification cases.

- [ ] **Step 4: Run all checks**

Run: `cd backend && pytest -q`

Run: `cd frontend && npm test -- --run && npm run build`

Run: `docker compose -f deploy/compose.yaml config`

Expected: all commands exit 0.

## Plan Self-Review

- Spec coverage: Tasks 1–3 provide deployment/security/data foundation; Tasks 4–6 cover recordings, media and reading stats; Tasks 7–9 cover imports, TTS, dictation and administration; Tasks 10–12 deliver the PWA and deployment validation.
- Placeholder scan: no `TBD`, `TODO`, “implement later”, or undefined dependency is used as a task instruction.
- Type consistency: `source_validated_at`, `source_missing_at`, `recording_id`, `word_list_version_id`, `ordered_item_ids_json`, and stable error codes are identical across the relevant tasks.
