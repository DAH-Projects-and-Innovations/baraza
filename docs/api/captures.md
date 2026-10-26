# Capture API contract

Contract between the frontend and the backend capture layer (`VexaAdapter`, #125-#128, #77).
The frontend already calls these endpoints (see `frontend/src/lib/api/captures.ts`); until they
exist it runs against a simulation (`NEXT_PUBLIC_USE_MOCK_API=true`).

**Status: proposal, to be confirmed by the backend.** If you change something, update this file and
the frontend in the same PR.

All bodies are JSON. Errors use FastAPI's default shape `{"detail": ...}`. The frontend only relies
on the HTTP status code.

## Endpoints

### `POST /captures`: start a capture

Request:

```json
{ "meeting_url": "https://meet.google.com/abc-defg-hij" }
```

Response `200` (or `201`):

```json
{ "capture_id": "c_01HZX..." }
```

- Calls `CaptureAdapter.start(meeting_url)`: the bot is requested and joins as a visible,
  clearly named participant (#128).
- Return as soon as the capture is created. Do not wait for the bot to be admitted.
- `422` if `meeting_url` is not a Google Meet link (`https://meet.google.com/xxx-xxxx-xxx`).
- `502`/`503` if the capture service (Vexa) is unreachable.

### `GET /captures/{capture_id}`: capture status

Response `200`:

```json
{ "capture_id": "c_01HZX...", "status": "capturing" }
```

`status` is one of the values of `CaptureStatus` (`backend/src/baraza/adapters/base.py`):

| Value | Meaning | UI |
|---|---|---|
| `waiting_admission` | Bot requested, not yet admitted to the meeting | "Waiting to be admitted", stop allowed |
| `capturing` | Bot in the meeting, segments flowing | "Capturing", stop allowed |
| `processing` | Capture ended, finalizing transcript and minutes | "Processing" |
| `done` | Everything finished, minutes can be read | "Capture complete", minutes shown |
| `failed` | Unrecoverable error | "Capture failed" |

- `404` for an unknown `capture_id`.
- The frontend polls this endpoint every 2 seconds and stops once it sees `done` or `failed`.
  These two are final: never leave them.
- Transitions are formalised in #77; the UI only needs this set of values.

### `POST /captures/{capture_id}/stop`: stop a capture

Response `200` with any JSON (e.g. `{}`).

- Calls `CaptureAdapter.stop(capture_id)`; the status then moves to `processing`.
- Stopping an already stopped or finished capture should be idempotent (`200`), not an error.
- `404` for an unknown `capture_id`.

## Link with the other endpoints

- **`capture_id` is also the `meeting_id`** used by the segment and minutes endpoints. The frontend
  reads `/meetings/{capture_id}/segments` while the capture runs, and
  `/meetings/{capture_id}/minutes` once the status is `done`. If you need two separate identifiers,
  add `meeting_id` to the responses above and tell the frontend.
- **Segments**: the adapter pushes Vexa segments to `POST /meetings/{meeting_id}/segments`
  (see [adapters.md](../adapters.md#streaming-segments), accepted fields include `segment_id`,
  `speaker_id`, `start_time`, `end_time`, `text`). The format actually exposed by Vexa must be mapped
  there; check it against a demo meeting.
- **Minutes**: `GET /meetings/{id}/minutes` returns the `Minutes` JSON
  (`backend/src/baraza/core/minutes.py`), or `404` until generated. Owned by the AI pipeline (#89).

## Rules

- The bot must be a visible participant with a clear name (#128). Participants are informed and
  agree before any capture.
- No transcript text, meeting links or secrets in logs. Receive Vexa events through a verified
  channel (#127).
- Core tests never call Vexa or Google Meet: mock the HTTP calls.
- These endpoints have no authentication yet. Add it before any deployment outside a local
  environment.

## Done when

- [ ] `POST /captures` with a Meet link returns a `capture_id`; an invalid link returns `422`.
- [ ] `GET /captures/{id}` follows `waiting_admission`, `capturing`, `processing`, `done`, and
      returns `failed` on error.
- [ ] `POST /captures/{id}/stop` ends the capture and moves it to `processing`; calling it twice is
      harmless.
- [ ] With `NEXT_PUBLIC_USE_MOCK_API` unset, the frontend runs the whole flow against the real
      backend.
