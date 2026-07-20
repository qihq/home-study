# Local-First Dictionary and Pronunciation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make common English and Chinese word lookup stable without AI and let users force a fresh pronunciation while preserving old cached audio.

**Architecture:** A read-only local lexicon service maps ECDICT and CC-CEDICT SQLite rows into the existing result schema before falling back to AI. Dictionary results carry source metadata, and audio regeneration creates a revisioned TTS asset rather than overwriting cache.

**Tech Stack:** Python 3.12 stdlib SQLite, FastAPI, Pydantic, SQLAlchemy, pytest, React, TypeScript, Vitest, Docker.

## Global Constraints

- ECDICT content is MIT licensed; retain its notice.
- CC-CEDICT content is CC BY-SA 3.0; display attribution and share-alike notice.
- Runtime word lookup must not depend on a public API.
- Preserve existing dictionary history and TTS asset ownership controls.
- Do not overwrite a previously playable pronunciation during regeneration.

## Execution Progress

- 2026-07-20: Tasks 3-4 pronunciation regeneration slice implemented. Normal playback reuses its deterministic cache; forced regeneration creates a new owned asset and preserves the old audio. Three focused backend security/cache tests, eleven frontend dictionary/router tests, and the production build pass. Local dictionary provenance UI remains pending until Tasks 1-2.
- 2026-07-20: Tasks 1-2 and provenance UI implemented. A reproducible builder locks ECDICT to `bc015ed2e24a` and records the CC-CEDICT checksum, producing a 100,044,800-byte read-only SQLite database with 770,611 English entries, 96,851 aliases, and 124,718 Chinese entries. Real-data integrity is `ok`; English exact/inflected lookup and simplified/traditional Chinese lookup pass. Twenty-one focused backend and twelve frontend tests pass. The `苹果` collision now prefers the lowercase-pinyin common noun and keeps the Apple company sense as an alternative.

---

### Task 1: Local Lexicon Adapter and Reproducible Data Preparation

**Files:**
- Create: `backend/app/services/local_dictionary.py`
- Create: `backend/scripts/build_local_dictionary.py`
- Create: `backend/tests/fixtures/local_dictionary.sql`
- Create: `backend/tests/test_local_dictionary.py`
- Modify: `backend/app/core/config.py`
- Modify: `deploy/Dockerfile`
- Modify: `frontend/public/animal-island/ATTRIBUTION.txt`

**Interfaces:**
- Produces: `LocalDictionary.lookup(text: str, source_language: Literal['en','zh']) -> LocalLookup | None`.
- Produces: `LocalLookup(result: DictionaryResult, source: Literal['ecdict','cc-cedict'])`.
- Adds setting: `APP_LOCAL_DICTIONARY_PATH`, default `/app/dictionary/local-dictionary.sqlite3`.

- [ ] **Step 1: Write failing exact, lemma, Chinese, and miss tests**

```python
def test_ecdict_exact_and_lemma_lookup(local_dictionary):
    assert local_dictionary.lookup('apple', 'en').result.primary_translation == '苹果'
    assert local_dictionary.lookup('apples', 'en').result.source_text == 'apple'

def test_cc_cedict_lookup_and_miss(local_dictionary):
    found = local_dictionary.lookup('苹果', 'zh')
    assert found.result.primary_translation == 'apple'
    assert found.source == 'cc-cedict'
    assert local_dictionary.lookup('不存在词条', 'zh') is None
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend; pytest tests/test_local_dictionary.py -q`

Expected: FAIL because the local adapter does not exist.

- [ ] **Step 3: Implement read-only provider mapping**

Open SQLite with `mode=ro`, normalize case/spacing, query ECDICT by exact word then lemma, and query CC-CEDICT by simplified/traditional form. Parse line-separated translations and POS without inventing examples.

```python
@dataclass(frozen=True)
class LocalLookup:
    result: DictionaryResult
    source: Literal['ecdict', 'cc-cedict']
```

- [ ] **Step 4: Add reproducible builder and attribution metadata**

The build script accepts pinned ECDICT CSV and CC-CEDICT text inputs plus output path, writes normalized indexed tables, records source version/checksum rows, and uses one transaction. The Docker build copies a prepared database supplied in `backend/dictionary-data`; it fails with a clear message if release data is absent rather than downloading mutable sources at runtime.

- [ ] **Step 5: Run adapter tests and commit**

Run: `cd backend; pytest tests/test_local_dictionary.py -q`

Expected: PASS.

```powershell
git add backend/app/services/local_dictionary.py backend/scripts/build_local_dictionary.py backend/tests/fixtures/local_dictionary.sql backend/tests/test_local_dictionary.py backend/app/core/config.py deploy/Dockerfile frontend/public/animal-island/ATTRIBUTION.txt
git commit -m "feat: add local English and Chinese dictionaries"
```

### Task 2: Local-First Lookup Orchestration

**Files:**
- Modify: `backend/app/schemas/dictionary.py`
- Modify: `backend/app/services/dictionary.py`
- Modify: `backend/app/api/dictionary.py`
- Modify: `backend/tests/test_dictionary.py`
- Modify: `backend/tests/test_dictionary_api.py`

**Interfaces:**
- Adds result fields: `result_source: Literal['ecdict','cc-cedict','ai']` and `source_attribution: str | None`.
- Preserves: `POST /api/dictionary/lookup`, history, and entry IDs.

- [ ] **Step 1: Write failing no-AI local lookup and fallback tests**

```python
def test_local_word_lookup_works_without_ai_configuration(client, headers, local_dictionary_path):
    response = client.post('/api/dictionary/lookup', json={'text': 'apple'}, headers=headers)
    assert response.status_code == 200
    assert response.json()['result_source'] == 'ecdict'

def test_sentence_without_ai_returns_specific_degraded_error(client, headers):
    response = client.post('/api/dictionary/lookup', json={'text': 'I like apples.'}, headers=headers)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'DICTIONARY_AI_REQUIRED'
```

- [ ] **Step 2: Run dictionary tests and confirm RED**

Run: `cd backend; pytest tests/test_dictionary.py tests/test_dictionary_api.py -q`

Expected: FAIL because lookup currently requires AI before checking local sources.

- [ ] **Step 3: Add source metadata to the schema and cache fingerprint**

```python
class DictionaryResult(BaseModel):
    # existing fields
    result_source: Literal['ecdict', 'cc-cedict', 'ai'] = 'ai'
    source_attribution: str | None = None
```

Include local source version/checksum in the cache fingerprint so data upgrades create new entries.

- [ ] **Step 4: Orchestrate local-first lookup**

Classify only a single lexical item as eligible for local lookup. Query local provider before reading AI settings. If local misses, use AI exactly as today when configured; otherwise return `DICTIONARY_AI_REQUIRED` for phrases/sentences or `DICTIONARY_LOCAL_MISS` for a word miss.

- [ ] **Step 5: Run backend dictionary tests and commit**

Run: `cd backend; pytest tests/test_dictionary.py tests/test_dictionary_api.py -q`

Expected: PASS.

```powershell
git add backend/app/schemas/dictionary.py backend/app/services/dictionary.py backend/app/api/dictionary.py backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py
git commit -m "feat: prefer local dictionary before AI fallback"
```

### Task 3: Forced Pronunciation Regeneration

**Files:**
- Modify: `backend/app/api/dictionary.py`
- Modify: `backend/tests/test_dictionary_api.py`

**Interfaces:**
- Extends `DictionaryAudioRequest` with `regenerate: bool = False`.
- Response remains `{ "asset_id": string }`.

- [ ] **Step 1: Write failing cache-bypass test**

```python
def test_dictionary_audio_regeneration_creates_a_new_asset(client, headers, monkeypatch):
    first = client.post(url, json={'regenerate': False}, headers=headers).json()['asset_id']
    second = client.post(url, json={'regenerate': True}, headers=headers).json()['asset_id']
    assert second != first
    assert client.get(f'/api/tts-assets/{first}/audio', headers=headers).status_code == 200
    assert client.get(f'/api/tts-assets/{second}/audio', headers=headers).status_code == 200
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `cd backend; pytest tests/test_dictionary_api.py -q`

Expected: FAIL because `regenerate` is ignored/rejected.

- [ ] **Step 3: Implement revisioned generation**

For normal requests, retain deterministic cache lookup. For regeneration, skip that lookup and add a nonce/revision suffix to the new cache key after successful synthesis. Insert the new asset without deleting or changing the old asset.

```python
cache_material = f'dictionary:v{AUDIO_VERSION}:{user.id}:{voice_key}:{text}'
if payload.regenerate:
    cache_material += f':regenerated:{uuid4()}'
cache_key = sha256(cache_material.encode()).hexdigest()
```

- [ ] **Step 4: Run API tests and commit**

Run: `cd backend; pytest tests/test_dictionary_api.py tests/test_tts_audio.py -q`

Expected: PASS.

```powershell
git add backend/app/api/dictionary.py backend/tests/test_dictionary_api.py
git commit -m "feat: regenerate dictionary pronunciation on demand"
```

### Task 4: Dictionary Result Source and Audio UX

**Files:**
- Modify: `frontend/src/features/dictionary/DictionaryResultCard.tsx`
- Modify: `frontend/src/features/dictionary/DictionaryPage.tsx`
- Modify: `frontend/src/features/dictionary/DictionaryPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Extends `DictionaryResult` with backend source metadata.
- Changes `onPlay(entryId, voiceVersionId, regenerate)` to accept a regeneration flag.

- [ ] **Step 1: Write failing source-label and regeneration tests**

```tsx
it('labels local results and requests forced pronunciation regeneration', async () => {
  render(<DictionaryPage onLookup={lookupEcdict} onPlay={play} onMarkUnknown={vi.fn()} />)
  await user.click(screen.getByRole('button', { name: '查询' }))
  expect(screen.getByText('本地词典 · ECDICT')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '重新生成发音' }))
  expect(play).toHaveBeenCalledWith(expect.any(String), undefined, true)
})
```

- [ ] **Step 2: Run frontend dictionary tests and confirm RED**

Run: `npm --workspace frontend test -- DictionaryPage.test.tsx App.test.tsx --run`

Expected: FAIL because result-source and regeneration UI do not exist.

- [ ] **Step 3: Add result provenance and stable error copy**

Replace the unconditional AI disclaimer with the source-specific labels. Change lookup failure copy so local provider misses, missing AI, and general server failures are distinguishable.

- [ ] **Step 4: Add playback/regeneration busy state**

Keep `播放发音` dominant and `重新生成发音` secondary. Disable both during a request. Pass `regenerate: true` only for the regeneration action and play the returned asset immediately.

```tsx
body: JSON.stringify({
  voice_version_id: voiceVersionId || null,
  regenerate,
})
```

- [ ] **Step 5: Run frontend tests/build and commit**

Run: `npm --workspace frontend test -- DictionaryPage.test.tsx App.test.tsx --run`

Run: `npm --workspace frontend run build`

Expected: PASS.

```powershell
git add frontend/src/features/dictionary/DictionaryResultCard.tsx frontend/src/features/dictionary/DictionaryPage.tsx frontend/src/features/dictionary/DictionaryPage.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "feat: show dictionary sources and regenerate audio"
```

### Task 5: Dictionary System Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/superpowers/plans/2026-07-20-local-dictionary-pronunciation-implementation.md`

**Interfaces:**
- Verifies and documents all prior tasks.

- [ ] **Step 1: Run automated verification**

Run: `cd backend; pytest -q`

Run: `npm --workspace frontend test -- --run`

Run: `npm --workspace frontend run build`

Expected: all commands PASS.

- [ ] **Step 2: Verify offline and fallback behavior manually**

Disable AI, query `apple` and `苹果`, and confirm ECDICT/CC-CEDICT labels. Query a sentence and confirm the AI-required message. Re-enable AI and confirm the same sentence succeeds with the AI label.

- [ ] **Step 3: Verify regeneration safety manually**

Play one pronunciation, regenerate it, confirm the returned asset ID changes, and confirm both old and new authenticated audio endpoints remain playable.

- [ ] **Step 4: Document data versions, checksums, licenses, and deployment path**

Add preparation commands and `APP_LOCAL_DICTIONARY_PATH` to deployment docs, plus visible ECDICT and CC-CEDICT attribution to the README.

- [ ] **Step 5: Mark completed checkboxes and commit documentation**

```powershell
git add README.md docs/DEPLOYMENT.md docs/superpowers/plans/2026-07-20-local-dictionary-pronunciation-implementation.md
git commit -m "docs: document local dictionary data and licensing"
```
