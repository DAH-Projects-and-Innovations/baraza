# Sprint 02: capture integration

For the frontend-compatible endpoints, Docker checks and current acceptance
status, see the [Sprint 03 handoff](sprint03-thierry.md).

Thierry's scope: #77, #126, #127 and #128, plus the control API needed for
frontend integration. The existing state machine, Vexa adapter and polling worker
are reused. The API and worker must use the same `BARAZA_DATABASE_URL`.

## HTTP contract

| Request | Result |
|---|---|
| `POST /meetings/{meeting_id}/capture` | 201, `{"capture_id":"42"}` |
| `GET /meetings/{meeting_id}/status` | 200, durable status and transition history |
| `POST /meetings/{meeting_id}/capture/stop` | 202, `{"status":"stopping"}` |
| `GET /meetings/{meeting_id}/segments` | 200, common transcript segments |

Start body: `{"meeting_url":"https://meet.google.com/abc-defg-hij"}`.
Use a fresh meeting ID for each capture. Duplicate starts return 409 before any
additional bot request. Invalid URLs return 422 before creating a meeting.
Disabled or unconfigured Vexa returns 503. Upstream start/stop failures return
502 without exposing upstream response bodies. A failed start records `error`.
An unknown meeting status returns 404; stopping an inactive capture returns 409.

Status response example:

```json
{
  "id": "demo-001",
  "status": "pending",
  "transitions": [
    {"from_status": null, "to_status": "pending", "at": "2026-11-10T10:00:00Z"}
  ]
}
```

The worker polls Vexa; reading status does not call Vexa. A successful stop only
acknowledges the stop request. `processing` is recorded after final transcript
ingestion. The frontend can poll status and segments while capture is active.
Start/stop are synchronous upstream calls; a timeout must not be automatically
retried with another meeting ID because a remote bot may already exist.

## Reproducible demo

1. Configure and start the optional Vexa profile as described in
   [Vexa setup](vexa-backend.md). Enable Vexa and start both API and worker.
2. Inform participants and obtain appropriate agreement before starting capture.
   The participant information flow belongs to #106.
3. Create a test Meet meeting and call the start endpoint with a new meeting ID.
4. Admit the bot; check its visible name against `BARAZA_VEXA_BOT_NAME` (default:
   `Baraza – note taker (transcribing)`). Poll status and segments.
5. Request stop or end the meeting. Check that the final segments are stored and
   status becomes `processing` with UTC transition timestamps.
6. Restart the worker during another capture and confirm that polling resumes.

The endpoints follow the existing backend's authentication model; they do not
add user authentication. Keep this POC deployment within a trusted environment.
No inbound Vexa webhook route is registered. Status ingestion uses authenticated
polling and trusted stored bot IDs.

## Validation evidence and remaining acceptance

- #77: all 36 status pairs tested, including forbidden transitions; history persists.
- #126: reusable adapter contract and mocked meeting ingestion tested.
- #127: polling checks bot identifiers and rejects mismatches; the webhook route is absent.
- #128: configured bot name verified in the outbound request. Visible rendering in a
  real Meet meeting remains unverified. Chat notice is unavailable in the pinned
  open-source Vexa core; participant information remains an organizer responsibility.
- HTTP integration: SQLite-backed lifecycle, duplicate protection, invalid URL,
  disabled service and sanitized upstream failures tested.

Local checks: 120 tests pass; Ruff lint/format and strict mypy pass.
These are simulated checks. They do not establish real Meet operation, a visible
bot, or end-to-end LLM/frontend completion. The complete Meeting model (#52),
participant information (#106), and minutes generation integration remain separate
dependencies. No GitHub issue has been closed by this implementation.
