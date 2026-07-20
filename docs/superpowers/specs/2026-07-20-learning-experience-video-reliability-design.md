# Learning Experience and Video Reliability Design

## Goal

Make recording, video review, dictation, and dictionary use feel like one clear Animal Island experience while removing the video-processing states that currently require a backend restart.

The work must preserve existing user recordings and the uncommitted fMP4 recovery changes already present in the workspace.

## Scope and Delivery Order

The implementation is split into independently testable phases:

1. Repair video processing reliability and status reporting.
2. Redesign Chinese and English recording flows, including duration and completion navigation.
3. Add a calendar-driven video library with live processing updates and online playback.
4. Simplify the dictation hierarchy and make the hidden answer panel interactive.
5. Add a local-first dictionary pipeline and pronunciation regeneration.

Each phase must leave the application usable on its own. Existing Animal Island UI assets under `frontend/public/animal-island` are reused; no unrelated visual library is introduced.

## Confirmed Product Decisions

- Dictionary lookup is local-first: mature dictionary data handles words, while AI handles phrases, sentences, and local misses.
- Recording completion does not auto-redirect. It presents a primary `返回主页` action and a secondary `去视频库查看` action.
- A recording in progress displays elapsed time as `MM:SS`, or `HH:MM:SS` after one hour.
- The whole `答案已隐藏` panel acts as the reveal control and shows the word after activation.
- The video library adds a month calendar. Selecting a date filters the list to videos recorded on that date.
- Ready videos play inline in the application.
- Users can force regeneration of dictionary pronunciation when the cached audio is unsatisfactory.

## Existing-State Findings

### Worker Offline False Positive

The worker writes its heartbeat only before claiming a job. FFmpeg assembly or transcoding can run longer than the health endpoint's 15-second freshness threshold. During that work the UI reports the worker as offline even though it is busy.

The job lease has a similar weakness. `locked_at` is set only when a job is claimed. A long-running healthy task can appear expired and become eligible for a second worker after five minutes.

### Failed Video Jobs Can Become Inconsistent

The video handlers catch `MediaError`, set the recording to `assemble_failed` or `transcode_failed`, and return normally. The runner then marks the job `succeeded` because no exception escaped. Startup repair only requeues `transcode_failed`; it does not comprehensively reconcile `assembling`, `assemble_failed`, or `transcoding` records.

This creates recordings that cannot advance until a process restart happens to repair part of the state. Previewing a video does not stop processing, but the video library loads only once, so the UI never observes later state changes while it remains open.

### Current UI Hierarchy

- The recording page is functionally dense but visually plain and has no elapsed timer.
- Completion exposes only one generic action wired to the existing back callback.
- The video library already has in-progress Animal Island styling and inline preview changes in the dirty worktree; these changes must be extended, not replaced.
- Dictation gives navigation and locked voice metadata similar visual weight to the current prompt and answer.
- Dictionary lookup currently refuses to run without AI configuration and labels every result as AI-generated.
- Dictionary audio always reuses a deterministic cache entry; the API has no explicit bypass flag.

## Architecture

### 1. Reliable Background Processing

Introduce a small worker activity reporter responsible for both the worker heartbeat file and the current job lease. The runner starts it while a job is executing and stops it in a `finally` block. It refreshes more frequently than both health and lease expiry thresholds. File updates use a temporary file followed by atomic replacement so the health endpoint never reads partial JSON.

Video handlers must report failure to the runner instead of returning as if processing succeeded. Expected media failures carry stable error codes. The runner applies bounded automatic retries with backoff while `attempts < max_attempts`; exhausted jobs become `failed`. The associated recording status stays aligned with the job:

| Job | Queued or running recording state | Retrying state | Exhausted state | Success state |
| --- | --- | --- | --- | --- |
| `assemble_video` | `assembling` | `assembling` | `assemble_failed` | `transcoding` |
| `transcode_video` | `transcoding` | `transcoding` | `transcode_failed` | `ready` |

The worker's reconciliation pass runs at startup and periodically while idle. It restores missing jobs for recordings in `assembling` or `transcoding`, retries retryable failed media jobs within their attempt limit, and does not duplicate queued or running jobs. A verified source file lets a `transcode_failed` recording resume at transcoding without repeating assembly.

The health response distinguishes `online`, `busy`, and `offline` worker states while retaining the current boolean for compatibility. The UI only shows an offline warning when the heartbeat is genuinely stale. Copy must explain automatic recovery and offer a manual retry only after attempts are exhausted; it must not instruct the user to restart a container during normal recovery.

### 2. Recording Page

Chinese and English routes render one shared themed component. The page uses existing Animal Island camera, leaf, map, wave, and background assets. The layout hierarchy is:

1. Compact language title and back action.
2. Large camera preview with a recording badge and elapsed duration overlay.
3. One dominant start or stop button.
4. Secondary camera-switch control.
5. Upload and processing explanation in a smaller status card.

Elapsed duration uses a monotonic start timestamp so delayed intervals do not accumulate drift. It starts at zero for a new capture, advances once per second while recording, and freezes when stop is requested. Switching cameras during an active recording must not reset it. A recovered session starts a new visible elapsed segment; previously recorded duration is not guessed from chunk counts.

The component clears its interval and media tracks on unmount. Upload, permission, and recovery errors keep the current safe IndexedDB behavior.

After successful submission, the camera and recording controls are replaced by a completion card. `返回主页` and `去视频库查看` are explicit callbacks supplied by the app router. Navigation is user-triggered and deterministic.

### 3. Calendar Video Library

The recordings API continues returning all records and adds no server-side calendar dependency for the expected family-sized data set. The frontend derives:

- available months;
- the number of Chinese and English recordings per day;
- the selected date's records;
- whether the selected date contains an official recording.

The calendar includes previous and next month controls, weekday headings, empty leading cells, an obvious today state, selected state, and markers for each language. Initially it selects the newest date that has a recording; if there are no recordings, it selects today.

Clicking a marked date filters the list below. A `显示全部` control clears the date filter. Ready records retain inline authenticated preview via `/api/recordings/{id}/preview`. Only one player opens at a time, and changing the selected date closes a player that is no longer visible.

While any record is in `assembling` or `transcoding`, or is in an automatic retry state, `VideosScreen` refreshes recordings and worker health every five seconds without replacing the current list with a loading screen. Polling stops when no work is pending. Rename, delete, official selection, retry, and completion refresh the list while preserving the chosen calendar month/date when possible.

### 4. Dictation Page

The active task is the page's visual center. The hierarchy is:

1. Progress indicator and current item number.
2. Large play-pronunciation button.
3. Large hidden-answer panel.
4. Correct and incorrect scoring after reveal.
5. Previous, next, and jump navigation.
6. Collapsible pronunciation and locked-voice settings.

The hidden panel is a semantic button, keyboard accessible, labelled `显示答案`, and visually contains `答案已隐藏` plus a short tap instruction. Activating it calls the existing reveal endpoint, then displays the current word. Once revealed, it is no longer an active reveal button.

The existing pronunciation source and regeneration behavior stays available inside a `发音设置` disclosure. Session snapshot names remain visible there but no longer interrupt the main exercise flow. Moving between items shows each item's stored reveal and score state.

### 5. Local-First Dictionary

Define a dictionary provider interface that returns the application's existing `DictionaryResult` shape plus a source identifier and attribution metadata.

Lookup order is:

1. Normalize text and detect direction.
2. For one English lexical item, query a bundled ECDICT SQLite database, including lemma fallback for inflected forms.
3. For one Chinese lexical item, query a bundled CC-CEDICT SQLite database.
4. If no local entry exists, or the input is a phrase or sentence, use the configured AI provider.
5. Cache the normalized result in the existing dictionary entry/history tables.

AI configuration is therefore optional for local word lookup. A local miss without working AI returns a specific message explaining that local lookup found no entry and sentence translation needs AI; it does not claim the whole dictionary is unavailable.

ECDICT supplies English words, phonetics, parts of speech, English definitions, Chinese translations, and lemma information. CC-CEDICT supplies simplified/traditional Chinese, pinyin, and English definitions. Provider adapters map only available facts and do not invent examples or usage notes. AI remains responsible for richer phrase and sentence output.

Dictionary results display one of:

- `本地词典 · ECDICT`
- `本地词典 · CC-CEDICT`
- `AI 辅助，请家长核对`

The application attribution area adds ECDICT's MIT notice and CC-CEDICT attribution under CC BY-SA 3.0. Dictionary data is built into a compact read-only SQLite asset during image construction or downloaded by an explicit reproducible preparation script; runtime lookup must not depend on public dictionary APIs.

### 6. Pronunciation Regeneration

Extend the dictionary audio request with `regenerate: boolean = false`. Normal playback keeps the deterministic cache behavior. When regeneration is requested:

1. Validate entry and voice ownership exactly as normal playback does.
2. Generate new audio even if a ready cache asset exists.
3. Store it with a revisioned cache key while leaving the old file valid for any existing references.
4. Return the new asset ID.
5. The frontend plays the returned audio and reports success or a specific TTS error.

The result card presents `播放发音` as the main audio action and `重新生成发音` as a smaller secondary action. Both respect the selected configured or custom voice. Buttons show a busy state and prevent duplicate requests.

## Error Handling and Recovery

- Browser recording chunks remain in IndexedDB until acknowledged and submitted.
- Navigation does not discard an unfinished local recording session.
- Worker heartbeats and job lease refresh errors are logged, but the active media subprocess is not killed solely because a status write failed.
- Retriable media failures use bounded exponential backoff. Invalid or missing input chunks are terminal until the source data changes or a user explicitly retries after repairing it.
- An exhausted video job exposes a `重新处理` action in the video card. The backend validates that the requested transition is safe and enqueues exactly one job.
- Calendar and video-list load failures preserve already loaded records.
- Local dictionary database absence is a distinct deployment/configuration error. AI fallback may still work, but the UI reports the degraded local provider.
- TTS regeneration failure leaves the previous playable cached pronunciation untouched.

## Testing

### Backend

- A slow fake video handler keeps heartbeat and lease timestamps fresh while running.
- Expired jobs remain reclaimable, but actively renewed jobs are not claimed twice.
- Media errors retry with backoff and keep recording/job statuses aligned.
- Reconciliation repairs every supported stuck video state without duplicate jobs.
- Successful assembly queues one transcode job; successful transcode reaches `ready`.
- The recordings retry endpoint accepts exhausted safe states and rejects recording, ready, or unsafe states.
- ECDICT exact and lemma lookups work without AI configuration.
- CC-CEDICT lookup works without AI configuration.
- Phrases, sentences, and local misses use AI when configured and return a clear local-miss response when not.
- Dictionary result source metadata and attribution are returned correctly.
- Normal pronunciation reuses cache; regeneration creates and returns a new owned asset.

### Frontend

- Recording duration starts, advances, survives camera switching, stops, and cleans up.
- Both language routes render the same themed structure with language-specific copy.
- Completion buttons route only to home or video library as selected.
- Calendar month navigation, daily markers, date filtering, and `显示全部` work.
- Processing records poll until ready and then expose inline playback without page reload.
- Offline, retrying, exhausted, and ready statuses have distinct copy.
- Clicking or keyboard-activating the hidden answer panel reveals the word.
- Pronunciation and voice controls are secondary while the current task stays prominent.
- Dictionary local and AI result labels render correctly.
- Pronunciation playback and forced regeneration show busy and error states.

### System Verification

- Run the full backend test suite.
- Run the full frontend test suite and production build.
- Record both Chinese and English videos in a real browser, verify timer and both completion destinations.
- Leave the video library open through assembly and transcoding, verify no false offline warning and automatic transition to playable state.
- Restart the worker during processing and verify lease recovery without duplicate final files.
- Verify ECDICT and CC-CEDICT entries with the AI provider disabled.
- Verify a sentence falls back to AI and a regenerated pronunciation differs by asset ID while the old asset remains playable.

## Rollout and Data Safety

- Do not delete original upload chunks as part of this work.
- Keep the current fMP4 reconstruction and validation changes intact.
- Database schema changes use Alembic migrations and remain backward compatible for existing dictionary history and TTS assets.
- Build dictionary data reproducibly and record source versions/checksums in attribution metadata.
- Deploy with the existing persistent `/data` mount unchanged.
- After deployment, inspect worker health, queued/running jobs, a recovered pending recording, and one newly recorded video before considering rollout complete.

## Success Criteria

- Active video processing no longer produces a false offline warning.
- A recoverable video proceeds without requiring a backend restart.
- Exhausted failures are visible and manually retryable without database edits.
- Recording duration is always visible during capture, and completion offers both approved destinations.
- The video library can select a day, list that day's check-ins, and play ready videos online.
- The hidden answer panel reveals the word when activated, and the dictation task is visually dominant.
- Common English and Chinese word lookups work with AI disabled.
- Dictionary pronunciation can be regenerated without destroying the prior cached audio.
- All new UI follows the existing Animal Island asset style and retains required attribution.
