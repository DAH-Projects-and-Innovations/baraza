# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Sprint 3 capture API integration with explicit consent, meeting persistence, validated final
  transcript ingestion, queued draft generation, retrieval and failed-generation retry.
- Published transcript/segment JSON Schemas with a CI drift check and a segment-export converter.
- Meeting title/template controls, live processing/error feedback, recovery pages and explicit
  simulation labels; `/meet/` Google Meet links are normalized to the canonical meeting URL.
- Internal demo runbook distinguishing backend rehearsal, browser fallback and pending real
  Google Meet/Vexa validation.

- Initial repository structure: backend (FastAPI, uv), frontend (Next.js), Docker Compose,
  documentation and continuous integration.
- Common transcript format (v1.0) and minutes schema.
- Capture adapter contract.
- Transcript segment format for live capture and segment ingestion (`POST/GET /meetings/{id}/segments`)
  with validation and database storage.
