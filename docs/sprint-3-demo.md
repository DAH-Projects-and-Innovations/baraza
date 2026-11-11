# Sprint 3: Lauriane and Nancy

Scope: internal MVP demonstration on **3 November 2026**. Code and automated tests are not
evidence that a real Google Meet capture has succeeded.

## Backlog audit (2 November 2026)

| Issue | GitHub state | Work in this branch | Remaining evidence |
| --- | --- | --- | --- |
| [#105](https://github.com/DAH-Projects-and-Innovations/baraza/issues/105) | Open | Title, Meet link, standard template, explicit consent, backend validation and redirect | Real adapter integration |
| [#160](https://github.com/DAH-Projects-and-Innovations/baraza/issues/160) | Open | Polling, stop, processing stage, draft, errors and generation retry | Live Vexa state transitions |
| [#40](https://github.com/DAH-Projects-and-Innovations/baraza/issues/40) | Open | Segment-export converter and rehearsal procedure | Consented real meeting, actual Vexa payload and gap report |
| [#93](https://github.com/DAH-Projects-and-Innovations/baraza/issues/93) | Open | Existing responsive shell retained; error and not-found recovery added | Full account/navigation scope deferred with authentication |
| [#111](https://github.com/DAH-Projects-and-Innovations/baraza/issues/111) | Closed | Publish both JSON Schemas and check drift in CI | Review schema compatibility with the actual capture producer |
| [#78](https://github.com/DAH-Projects-and-Innovations/baraza/issues/78) | Closed | Complete final-transcript validation, persistence and generation submission | Real capture payload validation |

The closed #78/#111 issues previously delivered segment models and ingestion through PRs
#188–#190. Their original descriptions also requested schema publication and generation
submission; these missing connections are included here. No issues are closed or reassigned by
this branch.

## Integration contract

`capture_id` is the `meeting_id` for this MVP.

| Endpoint | Behavior |
| --- | --- |
| `POST /captures` | `{meeting_url, title, template: "standard", participants_informed: true}` → 201, capture/meeting IDs, status, simulation flag |
| `GET /captures/{id}` | Status, title, processing stage, safe error message and whether generation can be retried |
| `POST /captures/{id}/stop` | Request provider stop; polling waits for its completed transcript, then validates, persists and enqueues; repeated stops are harmless |
| `POST /meetings/{id}/segments` | Existing live ingestion; preserves speaker IDs and rejects invalid segments individually |
| `POST /meetings/{id}/transcript` | Common final `Transcript` → 202; unsupported version, empty/invalid segments → 422 and failed state; already submitted → 409 |
| `GET /meetings/{id}/transcript` | Persisted canonical transcript, or 404 before availability |
| `GET /meetings/{id}/minutes` | Persisted AI draft, or 404 before availability |
| `POST /meetings/{id}/retry` | Retry failed generation using its stored transcript; other states → 409 |

The final transcript preserves participants and replaces live partial segments in the displayed
canonical transcript. Further live batches for that final transcript return 409. Only one active
arq generation job is submitted per meeting. The worker
calls the existing `generate_minutes` pipeline; it stores either a draft or a safe, actionable
failure. The draft is never automatically shared. Missing owners/deadlines remain null and the
interface renders “Not specified”. Generation quality and JSON robustness remain Luca's scope.

Capture providers implement `CaptureAdapter`. The included `fake` provider never joins Meet.
Default `BARAZA_CAPTURE_MODE=disabled` returns 503 rather than silently simulating live capture.

`BARAZA_CAPTURE_MODE=vexa` routes `POST /captures` to the real `VexaAdapter` (Google Meet bot).
It needs the Vexa profile running and `BARAZA_VEXA_API_KEY`; without a key the API answers 503.
After an API restart, an in-progress capture is re-registered from its meeting record, so status
and stop keep working. Stop only requests the end: the transcript is ingested once Vexa reports
the meeting as completed. Not yet exercised against a live Google Meet call.
Thierry's Vexa adapter must be wired into `get_capture_adapter()`; this branch does not claim to
deliver or validate it. Authenticated provider polling/event intake remains with that integration.
The MVP record is kept separately in `core/meeting_record.py` and the `meeting_records` table to
avoid colliding with the lifecycle model and `meetings` table introduced by PR #197.

## Rehearsal with the real backend and simulated capture

1. Copy `.env.example` to `.env` if no local configuration exists.
2. Set `BARAZA_CAPTURE_MODE=fake` and `NEXT_PUBLIC_USE_MOCK_API=false` in `.env`.
3. Configure the actual LLM gateway. For local Ollama use
   `BARAZA_LLM_BASE_URL=http://ollama:11434/v1` and `BARAZA_LLM_MODEL=mistral`.
4. Run `docker compose --profile local up -d --build`, then
   `docker compose exec ollama ollama pull mistral` on the first run.
5. Open `http://localhost:3000/meetings/new`. Enter a fictional title and syntactically valid
   Meet link, confirm consent, then start. The capture page must say it is simulated.
6. Stop capture. Observe processing, the fictional transcript and the generated AI draft.
7. Refresh the meeting URL. The transcript and draft must still be available.
8. Stop the model service for an error rehearsal. A failed generation must expose retry; restore
   the service and retry. Do not present this as a live Meet test.

PostgreSQL stores meeting metadata, consent confirmation, final transcript and draft. Redis/arq
requires the worker container to run. A worker crash or lost Redis queue can leave a meeting in
processing; inspect services and rerun the job during this internal POC. A durable outbox,
migrations and automatic recovery are follow-up work.

## Transparent browser-only fallback

Set `NEXT_PUBLIC_USE_MOCK_API=true` in `frontend/.env.local` and restart the development server
(or set the build argument and rebuild Docker). This mode simulates **capture, transcript and
minutes** inside the browser. The banner states that no bot joins Meet. No real backend or model
is exercised, and session state is only retained in the current browser session.

Announce: “This is the fallback with fictional data. The interface flow is demonstrated; live
capture and AI generation are not being validated.”

## Real meeting validation (#40)

Not executed by this branch: a test meeting and configured Vexa service are required, together
with participants' informed consent. Do not mark #40 complete based on synthetic tests.

1. Confirm the visible bot name, participant information/consent and test meeting link.
2. Launch from Baraza with browser simulation disabled and the real adapter configured.
3. Check admission, status updates, speaker metadata, timestamps and segment latency.
4. Stop capture; check canonical transcript, decisions/actions and nulls for missing information.
5. Verify each decision, owner and deadline against the actual transcript before sharing anything.
6. Record platform/adapter versions, run time, observed transitions, timestamp accuracy, speaker
   gaps, transcript availability delay and blocking errors in a private report.

For an export already mapped to the streaming segment contract, a standalone converter is
available (run in `backend/`):

```sh
uv run python scripts/convert_capture.py /private/capture.json /private/transcript.json \
  --meeting-id test-id --title "Internal test" --started-at 2026-11-02T10:00:00Z \
  --language fr --participants-informed
```

The input is `{"segments": [...]}` with stable `segment_id`, numeric `start`/`end` (or
`start_time`/`end_time`), text, optional source speaker ID and available speaker name. No timestamp
or identity is guessed; missing required metadata fails validation. This is not a claim that an
unmapped Vexa response is supported. Keep real transcripts and their converted output outside
the repository.

## Verification

```sh
cd backend
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python scripts/export_schemas.py --check
cd ../frontend
pnpm lint
pnpm test
pnpm typecheck
pnpm build
```

`test_sprint3_flow.py` covers start → ingestion → queued generation → persisted draft with
SQLite, the fake capture adapter, recording queue and `FakeLLMClient`. It also covers invalid
URLs, missing consent, unsupported schema versions, empty/invalid transcripts, repeated stops,
queue failure, failed-model retry, unknown meetings and browser CORS. It makes no live platform
or model calls. Passing these checks does not replace the real meeting rehearsal.

### Local results — 2 November 2026

Verification used Python 3.14 with the repository's locked dependencies and Node 24.

| Check | Result |
| --- | --- |
| Backend tests | 54 passed, including converter validation and private-input error handling |
| Ruff lint and formatting | Passed |
| mypy | Passed, 26 source files |
| Published JSON Schema drift check | Passed |
| Frontend URL tests | 2 passed |
| Frontend ESLint, route types and TypeScript | Passed |
| Next.js production build | Passed |
| New meeting page over HTTP | 200; title, consent and explicit simulation banner present |
| Compose configuration with `.env.example` | Valid; containers were not started for this verification |

The local pnpm launcher was broken, so frontend checks used the installed Node CLI entry points.
The Windows default pytest temporary directory was inaccessible; a new directory inside
`.pytest_cache` was used instead. Browser automation timed out, so visual interaction was not
independently verified. Actual Meet/Vexa validation is explicitly deferred until Thierry's
integration, as agreed; no real meeting link or transcript is stored in this branch.
