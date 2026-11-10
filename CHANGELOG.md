# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Async database lifecycle, transactional FastAPI sessions and named constraints.
- Alembic baseline and minutes migrations, a Compose migration gate, and CI schema drift checks.
- Versioned draft/validated minutes with JSONB content, provenance, revision history,
  optimistic locking and service-enforced immutability after validation.
- Stored minutes read endpoint (`GET /meetings/{id}/minutes`) with a version ETag.
- Opt-in Postgres/Redis integration infrastructure and tests.
- Frontend-compatible capture endpoints (`POST /captures`, `GET /captures/{id}`,
  `POST /captures/{id}/stop`) sharing the local meeting ID used by transcripts and minutes.
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
