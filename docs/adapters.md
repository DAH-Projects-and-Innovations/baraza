# Writing a capture adapter

An adapter connects a platform (Google Meet, Teams, Zoom…) or a source (file) to the core. You only
need to read two files:

- [`backend/src/baraza/adapters/base.py`](../backend/src/baraza/adapters/base.py): the
  `CaptureAdapter` interface;
- [`backend/src/baraza/core/transcript.py`](../backend/src/baraza/core/transcript.py): the common
  transcript format.

## Contract

| Method | Role |
|---|---|
| `capabilities()` | Supported platforms, real-time or not, whether speaker names are provided |
| `start(meeting_url)` | Start capturing, return a capture identifier |
| `stop(capture_id)` | Stop capturing |
| `status(capture_id)` | `waiting_admission`, `capturing`, `processing`, `done`, `failed` |
| `fetch_transcript(capture_id)` | Return a `Transcript` once capture is done |

## Rules

- Speakers are identified from meeting metadata, **never by voiceprint**. When unknown, use
  "Speaker 1", "Speaker 2"…
- If the adapter uses a bot, it must appear as a visible, clearly named participant.
- Adapter tests must not depend on a real video conferencing account: mock the HTTP calls.

## Streaming segments

Adapters that capture a live meeting push `TranscriptSegment` objects
([`core/segments.py`](../backend/src/baraza/core/segments.py)) while the meeting runs, instead of
returning one `Transcript` at the end.

| Field | Meaning |
|---|---|
| `meeting_id` | Meeting the segment belongs to |
| `segment_id` | Unique within the meeting; re-sending an id replaces the segment (a partial result is replaced by its final version) |
| `speaker` | Speaker name, or "Speaker 1", "Speaker 2"… when unknown |
| `speaker_id` | Optional stable speaker identifier from the source. If `speaker` is missing it is labelled "Speaker <id>"; identity is never guessed |
| `start`, `end` | Seconds from the meeting start (`end >= start`) |
| `text` | Non-empty, trimmed text |
| `language` | Optional ISO 639-1 code |
| `is_final` | `false` for a partial result that may still be revised |

The ingestion endpoint also accepts the source field names `start_time` and `end_time`.

`segments_to_transcript()` assembles the final segments into the `Transcript` used by the minutes
pipeline. Breaking changes bump `SEGMENT_SCHEMA_VERSION`.

## Planned adapters

| Adapter | Platforms | Transcription | Milestone |
|---|---|---|---|
| File import | All | Self-hosted Whisper | MVP |
| Native Google Meet transcript | Meet (Workspace Business Standard+) | Google | MVP, option A |
| Vexa bot | Meet, Teams, Zoom (experimental) | Self-hosted Whisper | MVP, option B |
| Native Teams transcript | Teams | Microsoft | After MVP |
| Native Zoom transcript | Zoom | Zoom | After MVP |

## Vexa implementation

The optional Google Meet adapter, pinned service deployment, polling and lifecycle mapping are
implemented. See [vexa-backend.md](vexa-backend.md) for configuration and remaining live checks.
The reusable mock-based contract is in `backend/tests/adapters/contract.py`.
