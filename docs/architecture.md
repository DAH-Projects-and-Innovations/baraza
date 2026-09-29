# Architecture

Baraza is organized in three layers. Only the core is developed in this repository; adapters and
surrounding services are replaceable.

| Layer | Role | Location |
|---|---|---|
| Capture adapters | Fetch a transcript from a platform or a file and convert it to the common format | `backend/src/baraza/adapters/` |
| Core | Common format, minutes generation, human validation, action tracking, search | `backend/src/baraza/core/` |
| Pluggable services | Language model (through an OpenAI-compatible API), transcription, storage | configuration (`.env`) |

## Principles

1. **Integrate rather than rebuild**: bots, transcription and models are external services.
2. **The core knows no platform**: it receives a `Transcript` (see `core/transcript.py`).
3. **The core knows no model**: it calls an OpenAI-compatible API configured through environment
   variables.
4. **Private by default**: a fully local deployment must always remain possible.
5. **Humans validate**: a draft is never shared without explicit validation.

## Main flow

1. An adapter captures the meeting and produces a `Transcript`.
2. The API stores the transcript and enqueues a task (Redis / arq).
3. The worker generates a `Minutes` draft with the configured model; the response is validated
   against the schema (`core/minutes.py`).
4. The organizer is notified, reviews, edits and validates.
5. The validated minutes are exported and their action items join the follow-up list.

## Components

| Component | Technology |
|---|---|
| API | FastAPI |
| Background tasks | arq + Redis |
| Database | PostgreSQL (native full-text search) |
| Web interface | Next.js |
| Language model | LiteLLM / Ollama / vLLM / hosted provider |
| Transcription (file import) | faster-whisper + pyannote.audio (planned) |
| Meeting bot (option B) | Vexa, official image at a pinned version, not forked |
