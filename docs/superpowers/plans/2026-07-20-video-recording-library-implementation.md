# Video Reliability, Recording, and Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make video jobs recover automatically, add an Animal Island recording timer/completion flow, and provide a calendar video library that updates until videos are playable.

**Architecture:** The worker renews a heartbeat and job lease during long FFmpeg calls and reconciles recording/job state both at startup and while idle. The React recording and library screens keep routing explicit and derive calendar state from the existing recording list API.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, pytest, React, TypeScript, Vitest, Testing Library, CSS, FFmpeg.

## Global Constraints

- Preserve all existing upload chunks and the dirty-worktree fMP4 reconstruction changes.
- Reuse only the existing assets under `frontend/public/animal-island` for the themed UI.
- Keep existing API fields compatible; additive fields are allowed.
- Do not require a container restart for recoverable media work.
- Keep the persistent `/data` deployment mount unchanged.

## Execution Progress

- 2026-07-20: Tasks 1-2 implemented. Focused backend verification passes: 23 worker, health, recording, fMP4, and download tests. The worker renews heartbeat/lease during work, media failures retry with backoff, stuck processing states are reconciled, and exhausted failures expose an authenticated retry endpoint.

---

### Task 1: Worker Activity and Retry State Machine

**Files:**
- Create: `backend/app/workers/activity.py`
- Modify: `backend/app/services/jobs.py`
- Modify: `backend/app/workers/runner.py`
- Modify: `backend/app/workers/video.py`
- Modify: `backend/app/api/health.py`
- Test: `backend/tests/test_jobs.py`
- Test: `backend/tests/test_worker_runner.py`
- Test: `backend/tests/test_health.py`
- Test: `backend/tests/test_video_worker.py`

**Interfaces:**
- Produces: `WorkerActivity(settings, worker_id, job_id=None)`, `touch_worker_heartbeat(...)`, `renew_job_lease(...)`, `reconcile_pending_work(session)`.
- Preserves: `run_once(session, worker_id, now=None) -> bool`.

- [ ] **Step 1: Write failing heartbeat and lease-renewal tests**

```python
def test_worker_activity_renews_running_job_lease(session, tmp_path, monkeypatch):
    job = Job(type='transcode_video', entity_id='r1', status='running')
    session.add(job); session.commit()
    touch_worker_heartbeat(tmp_path, 'worker-a')
    renew_job_lease(session, job.id, 'worker-a')
    session.refresh(job)
    assert job.locked_by == 'worker-a'
    assert job.locked_at is not None
    assert json.loads((tmp_path / 'worker-heartbeat.json').read_text())['worker_id'] == 'worker-a'
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `cd backend; pytest tests/test_jobs.py tests/test_worker_runner.py tests/test_health.py -q`

Expected: FAIL because activity renewal and detailed worker state do not exist.

- [ ] **Step 3: Implement atomic heartbeat and current-job lease renewal**

```python
def touch_worker_heartbeat(data_dir: Path, worker_id: str, *, busy: bool = False) -> None:
    target = data_dir / 'worker-heartbeat.json'
    partial = target.with_suffix('.json.part')
    partial.write_text(json.dumps({
        'worker_id': worker_id,
        'busy': busy,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }), encoding='utf-8')
    partial.replace(target)
```

Use a daemon thread with a stop event to call the heartbeat and lease updater every five seconds while a handler runs. Stop and join it in `finally`.

- [ ] **Step 4: Make media failures visible to the runner and retry with backoff**

```python
class MediaJobError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = True):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
```

Remove handler-level success returns after media errors. In the runner, queue retryable failures with `run_after = now + min(2 ** attempts, 60) minutes` while attempts remain; otherwise mark the job failed. Keep recording status `assembling` or `transcoding` while retrying and use `assemble_failed` or `transcode_failed` only when exhausted/terminal.

- [ ] **Step 5: Return detailed health while retaining compatibility**

```python
return {
    'status': 'ok',
    'worker': worker_state != 'offline',
    'worker_state': worker_state,
    'worker_updated_at': updated.isoformat() if updated else None,
}
```

- [ ] **Step 6: Run worker tests and confirm GREEN**

Run: `cd backend; pytest tests/test_jobs.py tests/test_worker_runner.py tests/test_health.py tests/test_video_worker.py tests/test_recording_download.py -q`

Expected: PASS, including existing fMP4 and independent-chunk coverage.

- [ ] **Step 7: Commit the state-machine slice**

```powershell
git add backend/app/workers/activity.py backend/app/services/jobs.py backend/app/workers/runner.py backend/app/workers/video.py backend/app/api/health.py backend/tests/test_jobs.py backend/tests/test_worker_runner.py backend/tests/test_health.py backend/tests/test_video_worker.py
git commit -m "fix: keep video processing alive and recoverable"
```

### Task 2: Recording Reconciliation and Manual Retry

**Files:**
- Modify: `backend/app/workers/runner.py`
- Modify: `backend/app/api/recordings.py`
- Test: `backend/tests/test_worker_runner.py`
- Test: `backend/tests/test_recordings.py`

**Interfaces:**
- Consumes: `enqueue_once(session, job_type, entity_id)` and aligned media states from Task 1.
- Produces: `POST /api/recordings/{recording_id}/retry` and `reconcile_pending_work(session)`.

- [ ] **Step 1: Write failing reconciliation and retry API tests**

```python
def test_reconcile_restores_missing_assemble_and_transcode_jobs(session):
    reconcile_pending_work(session)
    assert session.query(Job).filter_by(type='assemble_video', entity_id=assembling.id, status='queued').count() == 1
    assert session.query(Job).filter_by(type='transcode_video', entity_id=transcoding.id, status='queued').count() == 1

def test_retry_exhausted_transcode_uses_verified_source(client, headers):
    response = client.post(f'/api/recordings/{recording_id}/retry', headers=headers)
    assert response.status_code == 202
    assert response.json()['status'] == 'transcoding'
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend; pytest tests/test_worker_runner.py tests/test_recordings.py -q`

Expected: FAIL because all stuck states and the retry route are not supported.

- [ ] **Step 3: Reconcile periodically while idle**

Reconcile `assembling` with `assemble_video`; reconcile `transcoding` with `transcode_video`; convert retryable failed jobs under the attempt limit back to queued. Call reconciliation on startup and once per minute during idle worker loops. `enqueue_once` prevents duplicates.

- [ ] **Step 4: Add safe manual retry**

```python
@router.post('/recordings/{recording_id}/retry', status_code=202)
def retry_recording(...):
    if record.status == 'transcode_failed' and record.source_path:
        record.status = 'transcoding'; job_type = 'transcode_video'
    elif record.status == 'assemble_failed':
        record.status = 'assembling'; job_type = 'assemble_video'
    else:
        raise HTTPException(409, detail={'code': 'RECORDING_NOT_RETRYABLE'})
    reset_failed_media_job(session, job_type, record.id)
    session.commit()
    return {'status': record.status}
```

- [ ] **Step 5: Run focused tests and commit**

Run: `cd backend; pytest tests/test_worker_runner.py tests/test_recordings.py -q`

Expected: PASS.

```powershell
git add backend/app/workers/runner.py backend/app/api/recordings.py backend/tests/test_worker_runner.py backend/tests/test_recordings.py
git commit -m "fix: reconcile and retry stuck recordings"
```

### Task 3: Themed Recording Timer and Completion Routing

**Files:**
- Modify: `frontend/src/features/recording/RecordingPage.tsx`
- Modify: `frontend/src/features/recording/RecordingPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produces: `RecordingPage` props `onHome: () => void` and `onOpenVideos: () => void`.
- Preserves: chunk upload, IndexedDB recovery, camera switching, and `onBack` for pre-completion navigation.

- [ ] **Step 1: Write failing timer and completion tests**

```tsx
it('shows elapsed recording time and approved completion destinations', async () => {
  vi.useFakeTimers()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={home} onOpenVideos={videos} />)
  await user.click(screen.getByRole('button', { name: '开始录制' }))
  await vi.advanceTimersByTimeAsync(3100)
  expect(screen.getByText('00:03')).toBeVisible()
  // Complete mocked recording, then assert both explicit buttons.
  expect(screen.getByRole('button', { name: '返回主页' })).toBeVisible()
  expect(screen.getByRole('button', { name: '去视频库查看' })).toBeVisible()
})
```

- [ ] **Step 2: Run recording tests and confirm RED**

Run: `npm --workspace frontend test -- RecordingPage.test.tsx App.test.tsx --run`

Expected: FAIL because the timer and callbacks are absent.

- [ ] **Step 3: Implement drift-free elapsed time**

```tsx
const [elapsedMs, setElapsedMs] = useState(0)
const startedAt = useRef<number | null>(null)

useEffect(() => {
  if (state !== 'recording' || startedAt.current === null) return
  const update = () => setElapsedMs(performance.now() - startedAt.current!)
  update()
  const timer = window.setInterval(update, 250)
  return () => window.clearInterval(timer)
}, [state])
```

Start the timestamp only after `MediaRecorder.start`, freeze it before waiting for uploads, and never reset it during camera switching.

- [ ] **Step 4: Build the themed hierarchy and completion card**

Use existing `/animal-island/camera.svg`, `leaf.png`, `map.svg`, and `wave.svg`. Make the preview the visual focus, overlay the timer/recording badge, keep the dominant start/stop action below it, and render completion callbacks as separate buttons.

- [ ] **Step 5: Wire deterministic routes in App**

```tsx
<RecordingPage
  onBack={() => setScreen('home')}
  onHome={() => setScreen('home')}
  onOpenVideos={() => setScreen('videos')}
/>
```

- [ ] **Step 6: Run tests/build and commit**

Run: `npm --workspace frontend test -- RecordingPage.test.tsx App.test.tsx --run`

Run: `npm --workspace frontend run build`

Expected: PASS.

```powershell
git add frontend/src/features/recording/RecordingPage.tsx frontend/src/features/recording/RecordingPage.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "feat: redesign recording flow with elapsed time"
```

### Task 4: Calendar Library and Live Processing Updates

**Files:**
- Create: `frontend/src/features/recording/RecordingCalendar.tsx`
- Create: `frontend/src/features/recording/RecordingCalendar.test.tsx`
- Modify: `frontend/src/features/recording/VideoLibrary.tsx`
- Modify: `frontend/src/features/recording/VideoLibrary.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produces: `RecordingCalendar({ recordings, selectedDate, onSelectDate, onShowAll })`.
- Adds: `VideoLibrary` prop `onRetryProcessing?: (id: string) => Promise<void>`.

- [ ] **Step 1: Write failing calendar and polling tests**

```tsx
it('filters cards when a marked calendar day is selected', async () => {
  render(<VideoLibrary recordings={recordingsAcrossTwoDates} />)
  await user.click(screen.getByRole('button', { name: /2026年7月12日/ }))
  expect(screen.getByText('7月12日中文阅读')).toBeVisible()
  expect(screen.queryByText('7月13日英文阅读')).not.toBeInTheDocument()
})

it('polls pending recordings until they become ready', async () => {
  vi.useFakeTimers()
  render(<VideosScreenForTest />)
  await vi.advanceTimersByTimeAsync(5000)
  expect(api).toHaveBeenCalledWith('/recordings')
})
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `npm --workspace frontend test -- RecordingCalendar.test.tsx VideoLibrary.test.tsx App.test.tsx --run`

Expected: FAIL because the calendar and conditional polling are absent.

- [ ] **Step 3: Implement month grid and filtering**

Use local `YYYY-MM-DD` string parsing rather than UTC `Date` parsing. Mark Chinese and English counts independently, select the newest recorded date initially, close preview when its record is filtered out, and expose `显示全部`.

- [ ] **Step 4: Poll only while work is pending**

```tsx
const hasPending = videos.some(video => ['assembling', 'transcoding'].includes(video.status))
useEffect(() => {
  if (!hasPending) return
  const timer = window.setInterval(() => void load({ background: true }), 5000)
  return () => window.clearInterval(timer)
}, [hasPending])
```

Background loads preserve current records and do not show the empty loading state.

- [ ] **Step 5: Add precise status copy and retry action**

Map `assembling`/`transcoding` to processing, queued backoff to automatic retry, failed states to processing failed, and `ready` to playable. Only exhausted failures display `重新处理`, which calls the backend retry endpoint and refreshes.

- [ ] **Step 6: Run frontend verification and commit**

Run: `npm --workspace frontend test -- RecordingCalendar.test.tsx VideoLibrary.test.tsx App.test.tsx --run`

Run: `npm --workspace frontend run build`

Expected: PASS.

```powershell
git add frontend/src/features/recording/RecordingCalendar.tsx frontend/src/features/recording/RecordingCalendar.test.tsx frontend/src/features/recording/VideoLibrary.tsx frontend/src/features/recording/VideoLibrary.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "feat: add calendar video library with live updates"
```

### Task 5: Video End-to-End Verification

**Files:**
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/superpowers/plans/2026-07-20-video-recording-library-implementation.md`

**Interfaces:**
- Verifies all prior tasks; produces no new runtime interface.

- [ ] **Step 1: Run complete automated verification**

Run: `cd backend; pytest -q`

Run: `npm --workspace frontend test -- --run`

Run: `npm --workspace frontend run build`

Expected: all commands PASS.

- [ ] **Step 2: Run real media smoke checks**

Start the local app, record Chinese and English samples, wait on the open video library until both are ready, preview both inline, and verify the worker remains `online` or `busy`. Restart the worker during a third processing job and confirm it resumes without duplicate jobs/files.

- [ ] **Step 3: Document actual deployment and recovery behavior**

Add health states, automatic retry semantics, exhausted failure retry steps, and NAS verification commands to `docs/DEPLOYMENT.md`.

- [ ] **Step 4: Mark completed checkboxes and commit documentation**

```powershell
git add docs/DEPLOYMENT.md docs/superpowers/plans/2026-07-20-video-recording-library-implementation.md
git commit -m "docs: record video processing recovery workflow"
```
