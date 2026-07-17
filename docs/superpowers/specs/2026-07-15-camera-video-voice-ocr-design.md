# Camera, Video, Voice, and OCR Improvements

## Scope

Improve the existing family learning application in four related areas:

1. Chinese and English reading check-in camera selection.
2. Viewing, saving, and deleting completed check-in videos.
3. Clear lifecycle feedback for custom voice recordings.
4. Image-based spelling recognition with configurable cloud AI.

## Camera Selection

The recording page starts with the front camera and provides a visible control to switch between front and rear cameras before or during recording. Switching stops the current media stream, opens a stream with the requested `facingMode`, and updates the preview. If the requested camera is unavailable, the app preserves the active stream where possible and displays a clear permission or availability error.

## Video Library

The video library remains the place to review completed recordings. Each ready 720p recording provides a `Save to phone` action that downloads the generated video so the mobile browser can use its native download/save flow. Download errors are shown in the UI.

Each recording also provides a delete action behind a confirmation dialog. Deletion removes the recording record, its chunks, and server-side source/compressed assets. A recording cannot reappear in the library after a successful deletion.

## Custom Voice Feedback

Submitting a recording or an audio file immediately shows that the sample has been submitted for processing. The voice list presents localized statuses: processing, ready to preview/select, or failed. The client refreshes voice status while processing and displays a safe, actionable failure message; it does not claim the recording is already active. A voice becomes active only after processing succeeds and the user selects it as the default voice.

## Spelling Image Recognition

The spelling workflow gains image capture/upload, recognition progress, and an editable result-confirmation step before recognized words enter a word list. Images are sent only to the selected cloud AI provider. The backend requests a structured list of English words from a vision-capable model, validates and normalizes the returned words, and reports configuration, network, and invalid-image failures distinctly.

## OCR AI Configuration

System settings add a `Spelling recognition AI` section with a mode selector:

- `Use dictionary AI`: reuse the current dictionary AI credentials and endpoint.
- `Use separate AI`: configure a separate OpenAI-compatible visual AI provider with display name, endpoint, model, API key, temperature, timeout, enable state, and connection test.

The app resolves the selected configuration at recognition time. It rejects recognition when the selected configuration is absent, disabled, or lacks an API key. A separate configuration is recommended for a vision-capable model, while reuse is available for users whose existing dictionary provider supports image input.

## Data and API Changes

- Add recording deletion API and associated service cleanup.
- Extend video-list presentation only as needed for save/delete availability.
- Add OCR provider configuration persistence, encrypted API-key storage, settings endpoints, and a connection test.
- Add authenticated spelling-image recognition endpoint accepting an image upload and returning normalized candidate words.
- Extend existing frontend API types and pages to surface these operations and their states.

## Error Handling and Testing

- Browser tests cover initial and switched camera constraints, save/delete controls, upload feedback, and recognition confirmation flow.
- API tests cover deleting assets/records, AI configuration selection, missing or disabled configuration, and validated OCR results.
- Existing recording, voice, and dictionary behavior remains covered by the full frontend and backend suites.
