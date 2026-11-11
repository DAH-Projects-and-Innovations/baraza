# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `BARAZA_CAPTURE_MODE=vexa`: `POST /captures` now starts the real Vexa bot through `VexaAdapter`;
  in-progress captures survive an API restart and the Vexa HTTP client is closed at shutdown.
- Resilient LLM client and anti-invention checks in minutes generation; corrections are kept
  with the draft so reviewers can see what was removed or nulled.
- Sprint 3 capture API integration with explicit consent, meeting persistence, validated final
  transcript ingestion, queued draft generation, retrieval and failed-generation retry.
- Published transcript/segment JSON Schemas with a CI drift check and a segment-export converter.
- Meeting title/template controls, live processing/error feedback, recovery pages and explicit
  simulation labels; `/meet/` Google Meet links are normalized to the canonical meeting URL.
- Internal demo runbook distinguishing backend rehearsal, browser fallback and pending real
  Google Meet/Vexa validation.

- Async database lifecycle, transactional FastAPI sessions and named constraints.
- Alembic baseline and minutes migrations, a Compose migration gate, and CI schema drift checks.
- Versioned draft/validated minutes with JSONB content, provenance, revision history,
  optimistic locking and service-enforced immutability after validation.
- Versioned minutes read endpoint (`GET /meetings/{id}/minutes/stored`) with a version ETag;
  `GET /meetings/{id}/minutes` still serves the meeting record until the worker writes versions.
- Opt-in Postgres/Redis integration infrastructure and tests.
- Configurable browser origins and build-time frontend API/mock settings in Compose.
- Vexa Compose validation and an opt-in real health probe (`backend/scripts/check_vexa.py`).
- Capture control API: start and stop Vexa capture, and read durable meeting status with
  transition timestamps. Duplicate starts are rejected before creating another bot.
- Initial repository structure: backend (FastAPI, uv), frontend (Next.js), Docker Compose,
  documentation and continuous integration.
- Common transcript format (v1.0) and minutes schema.
- Capture adapter contract.
- Transcript segment format for live capture and segment ingestion (`POST/GET /meetings/{id}/segments`)
  with validation and database storage.

### Fixed

- Report an admitted Vexa bot as capturing even when its transcript is not available yet.
- Reject blank bot display names.
