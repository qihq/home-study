# Configurable TTS Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide secure, UI-managed MiMo and OpenAI-compatible TTS configuration.

**Architecture:** Store public configuration and encrypted API key in SQLite, expose a masked API, and resolve the selected adapter for workers and manual tests. The responsive settings page saves the configuration and plays a test sound.

**Tech Stack:** FastAPI, SQLAlchemy, Fernet encryption, React, Vitest, Docker Compose.

## Global Constraints

- API keys are encrypted at rest and never returned by an API response.
- MiMo remains the default protocol with configurable model, voice, endpoint, and speed.
- OpenAI-compatible TTS supports a custom base URL and model.
- The UI works at iPhone, iPad, and desktop widths.

### Task 1: Secure Backend TTS Configuration

**Files:** `backend/app/models/tts_provider_config.py`, `backend/app/services/tts_config.py`, `backend/app/api/settings.py`, `backend/tests/test_tts_settings.py`

- [ ] Write failing API tests for masked key reads and save-without-key retention.
- [ ] Run `python -m pytest backend/tests/test_tts_settings.py -q` and confirm failure.
- [ ] Add the encrypted configuration model, Fernet service, read/update API, and validation.
- [ ] Run the focused backend tests and confirm success.

### Task 2: Protocol Adapters And Worker Selection

**Files:** `backend/app/services/openai_tts.py`, `backend/app/services/tts.py`, `backend/app/workers/tts.py`, `backend/tests/test_tts_settings.py`

- [ ] Write failing tests for protocol-specific cache keys and adapter selection.
- [ ] Run the focused test and confirm failure.
- [ ] Implement OpenAI-compatible synthesis and resolve worker configuration from the stored provider.
- [ ] Run the focused backend tests and confirm success.

### Task 3: Responsive Settings UI

**Files:** `frontend/src/features/settings/SettingsPage.tsx`, `frontend/src/features/settings/SettingsPage.test.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

- [ ] Write a failing test for protocol selection and a password field that starts empty.
- [ ] Run `npm --workspace frontend test -- SettingsPage.test.tsx --run` and confirm failure.
- [ ] Implement configuration load/save/test controls and responsive form layout.
- [ ] Run the focused frontend tests and production build.

### Task 4: Local Deployment Verification

**Files:** `deploy/compose.yaml`

- [ ] Run full backend and frontend checks.
- [ ] Rebuild `family-learning-*` images and deploy locally on port 8011.
- [ ] Verify `/api/setup/status` returns 200 and record container status.
