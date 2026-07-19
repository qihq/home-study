# fMP4 Recording Assembly and Recovery Design

## Goal

Preserve the complete duration of browser reading recordings, including Safari/iOS fragmented MP4 output, and safely recover previously truncated NAS exports from their retained upload chunks.

## Root Cause

The browser calls `MediaRecorder.start(4000)`, producing one blob about every four seconds. Safari/iOS MP4 output is a single fragmented MP4 stream: the first blob contains initialization boxes, while later blobs contain dependent media fragments. The worker currently presents every blob to FFmpeg's concat demuxer as an independent MP4. FFmpeg reads the initialized first blob but cannot open later dependent blobs, so it can still produce a valid-looking file approximately one blob long. Validation only requires positive duration, allowing the truncated output to become the official source and 720p download.

The existing multi-chunk test duplicates complete standalone MP4 files. It therefore exercises concat of independent files rather than Safari's dependent fMP4 fragment layout.

## Assembly Design

The worker will inspect ISO Base Media File Format top-level boxes without decoding media. If the first chunk contains MP4 initialization (`ftyp`/`moov`) and later chunks contain media fragments (`moof`/`mdat`) without their own initialization, the assembler will concatenate the chunk bytes in sequence. This reconstructs the original fMP4 stream exactly.

If every MP4 chunk is independently probeable, the existing FFmpeg concat/remux path remains available. Unsupported or ambiguous layouts fail assembly instead of silently producing a partial recording. Single chunks continue to be copied as-is.

The assembler will probe input chunks where possible and calculate an expected lower-bound duration. For dependent fMP4 fragments, it will parse fragment decode timelines from `moof` metadata. The final source must have video and audio streams, positive duration, and a duration consistent with the assembled fragment timeline. FFmpeg output that silently stops after the first fragment is rejected.

## Recovery Design

Recovery runs against the NAS deployment data, using the database's ordered `recording_chunks` rows as the authoritative chunk list. Before mutation it creates a timestamped backup of the SQLite database and existing `source.mp4`/`720p.mp4` assets.

For each multi-chunk recording whose verified/exported duration is materially shorter than its fMP4 fragment timeline, recovery will:

1. Assemble a candidate file beside the current source without overwriting it.
2. Validate audio/video streams, full duration, and decoding near the beginning, middle, and end.
3. Transcode a candidate 720p file and apply the same validation.
4. Atomically promote both candidates while preserving timestamped backups.
5. Update `verified_duration_ms`, paths, validation timestamp, and ready status in one database transaction.

If chunks are missing, hashes do not match, the media layout is unsupported, or candidate validation fails, that recording is left unchanged and reported for manual review.

## Deployment

After local backend tests and a production frontend build pass, build a new Docker image from the fixed workspace. Transfer or build the image for the NAS deployment, update the deployed services without changing the persistent `/data` mount, then verify health and worker operation. No credential is stored in the repository or deployment configuration.

## Testing

- Generate a fragmented MP4 fixture with multiple dependent fragments using FFmpeg.
- Split it at top-level fragment boundaries to match Safari MediaRecorder behavior.
- Demonstrate that the old concat-demuxer approach truncates or fails to include the full duration.
- Assert the worker reconstructs a source whose duration matches the original within a small tolerance.
- Retain the independent MP4 chunk test and strengthen it to assert summed duration.
- Run the full backend suite and frontend production build.
- On NAS, compare chunk timeline, recovered source duration, and recovered 720p duration before promoting candidates.

## Safety and Success Criteria

- Existing NAS files are backed up before replacement.
- A candidate never replaces a current asset unless full validation succeeds.
- Previously truncated recordings with complete chunks recover to their original approximate duration.
- Newly recorded fMP4 sessions export at their full recorded duration.
- Independent MP4 chunks and single-chunk recordings continue to work.
