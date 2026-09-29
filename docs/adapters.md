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

## Planned adapters

| Adapter | Platforms | Transcription | Milestone |
|---|---|---|---|
| File import | All | Self-hosted Whisper | MVP |
| Native Google Meet transcript | Meet (Workspace Business Standard+) | Google | MVP, option A |
| Vexa bot | Meet, Teams, Zoom (experimental) | Self-hosted Whisper | MVP, option B |
| Native Teams transcript | Teams | Microsoft | After MVP |
| Native Zoom transcript | Zoom | Zoom | After MVP |
