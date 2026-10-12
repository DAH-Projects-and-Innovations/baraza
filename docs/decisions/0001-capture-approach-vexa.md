# ADR 0001: Capture approach for the proof of concept (Vexa)

- **Status**: proposed (to be validated by the team at kickoff)
- **Issue**: #32
- **Date**: 2026-10-13

## Context

Baraza needs a transcript to generate minutes. The POC must cover the path
Google Meet → capture → real-time transcript → structured minutes, with a meeting link entered
manually (calendar and browser extension integrations are out of scope for now).

Capture options listed in [adapters.md](../adapters.md):

| Option | Platforms | Transcription | Real time | Constraint |
|---|---|---|---|---|
| A. Native Google Meet transcript | Meet | Google | No | Requires Workspace Business Standard or higher |
| B. Vexa bot | Meet, Teams, Zoom (experimental) | Self-hosted Whisper | Yes | Self-hosted service to operate |
| File import | All | Self-hosted Whisper | No | No live meeting |

## Decision

Use **Vexa (option B)** for the POC, behind the existing `CaptureAdapter` interface
(`VexaAdapter`: start, stop, status, fetch transcript).

Why:

- works with any Google account, no Workspace plan required;
- provides segments in near real time, which the live meeting status screen needs;
- self-hosted, which keeps a fully local deployment possible (principle 4);
- reusable for Teams and Zoom later.

## Consequences

- Vexa runs as an external service, official image at a pinned version, **not forked**.
- The core never depends on Vexa: it only receives a `Transcript`. Other capture methods
  (option A, file import) stay possible by adding adapters.
- The bot must be a visible, clearly named participant; participants are informed and consent
  before any capture (see [gdpr.md](../gdpr.md)).
- Tests mock Vexa HTTP calls; no real meeting in CI.
- Segment format exposed by Vexa must be checked against the common segment schema (#111).
  Mapping happens in the adapter.
- Vexa licensing must be re-checked against the Apache-2.0 compatibility rule in
  [CONTRIBUTING.md](../../CONTRIBUTING.md) before it ships in `docker-compose.yml`.

## Open points

- Exact pinned Vexa version and deployment mode (to settle with #124).
- Webhook vs polling for status events (#127).
