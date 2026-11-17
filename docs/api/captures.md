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
  (`backend/src/baraza/core/minutes.py`), or `404` until generated. It carries an `ETag` (the
  version) and `X-Minutes-Status` (`draft` or `validated`).

## Meeting history and minutes review

There is no user authentication yet: every action is attributed to `local-user`.

| Endpoint | What it does |
|---|---|
| `GET /meetings?status=&needs_review=&limit=&offset=` | History, most recent first. Each item has the title, capture status, duration, participants, minutes status and version, and counts (decisions, actions, actions without owner or deadline). `needs_review=true` lists drafts waiting for a person. |
| `GET /meetings/{id}/minutes/meta` | Minutes status, version, who validated and when, prompt version, the model name, the anti-invention corrections and the counts. |
| `PUT /meetings/{id}/minutes` | Save an edit of the draft. Body is the `Minutes` JSON. Send the version you started from in `If-Match`. |
| `POST /meetings/{id}/minutes/validate` | Validate the draft. `If-Match` is required. |
| `GET /meetings/{id}/minutes/revisions` | Every saved version: who, when, draft or validated. |
| `GET /meetings/{id}/minutes/revisions/{version}` | The full minutes of one version. Version 1 is always the assistant's original. |
| `POST /meetings/{id}/minutes/regenerate` | Asks the model for a new draft (`202`, the capture goes back to `processing`). The previous draft, with any manual edits, stays in the revisions and the new one is the next version. `404` no draft yet, `409` the minutes are validated or a generation is running, `503` the queue is unavailable. If the model fails, the previous draft is kept and `error` explains it. |
| `POST /meetings/{id}/speakers/rename` | `{from_name, to_name}`. Names a speaker the capture could not name (`Speaker 3`). Applied to every line of that speaker and to the draft's action owners (a new minutes version when an owner changed). `404` unknown speaker, `409` the minutes are validated and locked, `422` empty, identical or too long name. Naming a speaker with the name of another one merges them. |

Errors: `428` no `If-Match`, `400` it is not a number, `412` stale version (the response `ETag`
is the current one: reload, then retry), `409` the minutes are validated and locked, `404` no
minutes yet, `422` an item cites a transcript segment that does not exist. Saving identical
content does not create a version.

The `status` of a listed meeting is the stored one, refreshed when the capture is read through
`GET /captures/{id}`.

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
