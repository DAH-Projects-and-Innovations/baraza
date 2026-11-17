# Sprint 03: Thierry's MVP Core handoff

Scope: #124, #125, #126, #127, #77 and #128. This work builds on the
Sprint 02 control API and the existing Vexa integration. It supports an internal
demo; minutes generation and frontend product work remain with their owners.

## What changed

- The backend now serves the current frontend contract: `POST /captures`,
  `GET /captures/{id}` and `POST /captures/{id}/stop`.
- The returned `capture_id` is a local meeting UUID, shared by status, segments
  and minutes URLs. It is deliberately different from the remote Vexa bot ID.
  The earlier `/meetings/{id}/capture` endpoint still returns the remote ID;
  callers of that endpoint must keep using their own meeting ID for local reads.
- Browser access allows the origins in `BARAZA_CORS_ORIGINS`, a JSON array
  defaulting to `["http://localhost:3000"]`. Other origins are not granted CORS.
- Docker builds receive `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_USE_MOCK_API`.
  Changes to either require rebuilding the frontend, because Next.js embeds them.
- An admitted bot becomes `capturing` immediately, even if the first transcript
  read fails. Polling retries the transcript on the next sweep without losing
  the capture handle. Blank bot names are rejected.
- Compose CPU/GPU configuration checks run in CI. A standalone script can also
  start Vexa and probe its real health endpoints without joining a meeting.

## Status contract

`GET /captures/{id}` returns `capture_id`, `status`, `meeting_status` and
`transitions`. Business state remains authoritative in `meeting_status`.

| Business state | Frontend capture status |
|---|---|
| pending | waiting_admission |
| capturing | capturing |
| processing | processing |
| draft_ready, validated | done |
| error | failed |

`done` means a draft is available; it does not mean a human validated it.
Stopping returns 202 with `{"status":"stopping"}`. It does not prematurely
advance the meeting to `processing`. The polling worker waits for the final
transcript, ingests it, and records that transition. API and worker must share
the same database. The LLM owner must integrate the next transition to
`draft_ready` and expose minutes; this capture implementation does not generate
or fabricate a report.

## Run the real Vexa health check (#124)

Requirements: Docker running, at least 15 GiB of free host disk space, about
8 GiB available RAM and 4 CPU cores. These are initial operating budgets, not
measured production guarantees. CPU works on macOS; CUDA requires Linux/NVIDIA.
Meet and model downloads require outbound access, so Vexa and Whisper have an
egress network. Their ports are never published; the Vexa database has only the
internal network. See [deployment details](vexa-backend.md) for image pins and GPU setup.

From the repository root, create `.env` from `.env.example` if it does not
already exist, and replace the three Vexa placeholder secrets. Validate first:

```bash
python3 backend/scripts/check_vexa.py --env-file .env
python3 backend/scripts/check_vexa.py --env-file .env --gpu
```

The second command only checks the GPU configuration; it does not require a GPU.
To start the CPU profile and check gateway, admin API, meeting API, runtime and
Whisper health endpoints:

```bash
python3 backend/scripts/check_vexa.py --env-file .env --start
```

This starts only Vexa and its dependencies, retaining their data volumes. It
prints success only after all probes pass. The gateway health probe does not
prove that a Meet bot can join or that Whisper model weights are ready.
The script refuses to start when host free space is below 15 GiB.

## Connect the frontend to capture

After Vexa is healthy, retrieve its provisioned scoped key locally:

```bash
docker compose --profile vexa exec vexa cat /run/vexa/key.env
```

Copy the key to `BARAZA_VEXA_API_KEY` in `.env`; never paste it into tickets or
logs. Set `BARAZA_VEXA_ENABLED=true`, `NEXT_PUBLIC_USE_MOCK_API=false` and the
browser-reachable `NEXT_PUBLIC_API_URL`. If using a remote demo host, update
`BARAZA_CORS_ORIGINS` to its frontend origin. Then:

```bash
docker compose --profile vexa up -d --build api worker frontend
```

For a real meeting: inform participants, obtain appropriate agreement, enter a
test Meet URL, admit the bot and check its configured visible name. Confirm live
segments and `capturing`, request stop, then confirm final ingestion and
`processing`. Restart the worker during another capture to verify recovery.
The pinned Vexa core has no chat-send implementation; #106 must provide the
participant information flow.

## Evidence and open acceptance

| Issue | Evidence | Remaining acceptance |
|---|---|---|
| #124 | Official version/digest verified; CPU/GPU Compose validation passes | Successful startup and health probes on a host with adequate disk space |
| #125 | Mocked authentication, timeout, retry, typed response and error tests pass | Real authenticated deployment check |
| #126 | Adapter contract, ingestion, restart, delayed transcript and terminal-state tests pass | Authorized real Meet capture |
| #127 | Authenticated outbound polling; unknown/mismatched IDs refused; no webhook route | Runtime polling confirmation |
| #77 | Every one of 36 state pairs tested; UTC history survives reload | Review and integration with the full Meeting model |
| #128 | Configured name sent to Vexa; blank names refused | Visually confirm the bot name in a real meeting |

On 10 November 2026, Docker Desktop was started and an isolated
`baraza-sprint03-check` project attempted to pull the pinned images. Extraction
failed with an input/output error while host free space was approximately
117 MiB. No successful runtime health result is claimed. No current test Meet
link was available. No meeting was joined, and no issue was closed or published.
No unrelated Docker data was removed to make room.

Local verification: 133 backend tests pass; Ruff lint/format and strict mypy pass.
CPU and GPU Compose validation both pass. The frontend image has not been built
locally during this sprint because of the disk constraint; CI retains its image
build check.

If live capture is unavailable, use the existing fictional transcript simulator:

```bash
cd backend
uv run python scripts/simulate_meeting.py demo-fictional --api http://localhost:8000
```

It exercises segment ingestion only. Label this fallback as simulated: it does
not exercise Vexa, create a capture status, or generate minutes. The frontend's
`NEXT_PUBLIC_USE_MOCK_API=true` mode is also explicitly simulated.
