# End-to-end test on a real Google Meet (issue #40)

A manual run of the whole chain with a real call, the Vexa bot and a real model. Nothing in the
automated tests proves this path: they use a mocked Vexa and a fake model. Fill in the result
column as you go and attach the filled table to #40.

Two people are needed: one organiser who starts the assistant, one participant who can admit it
and speak. Use a throwaway meeting and tell everyone it is a test.

## 0. Before you start

| Check | How | Result |
|---|---|---|
| Docker runs, 8 GB of free memory or more | `docker info` | |
| `development` is up to date | `git pull` | |
| A Google account that can create a Meet | | |

## 1. Configure

1. `cp .env.example .env`, then set:
   - `BARAZA_CAPTURE_MODE=vexa`
   - `BARAZA_VEXA_ENABLED=true`
   - `NEXT_PUBLIC_USE_MOCK_API=false`
   - `BARAZA_LLM_BASE_URL=http://ollama:11434/v1` and `BARAZA_LLM_MODEL=mistral`, or a hosted
     provider you trust for a test (then set `BARAZA_LLM_IS_EXTERNAL=true`).
   - Change `POSTGRES_PASSWORD` and the three `VEXA_*` secrets.
2. Start the services: `docker compose --profile vexa --profile local up -d --build`
3. First run only: `docker compose exec ollama ollama pull mistral`
4. Get the Vexa key: `docker compose exec vexa cat /run/vexa/key.env`. Copy `VEXA_API_KEY` into
   `BARAZA_VEXA_API_KEY` in `.env`, then `docker compose up -d --force-recreate api worker`.
5. Rebuild the frontend if you changed `NEXT_PUBLIC_*`: `docker compose up -d --build frontend`.

| Check | How | Result |
|---|---|---|
| API answers | `curl -s localhost:8000/health` | |
| Vexa is healthy | `docker compose --profile vexa ps` shows `healthy` | |
| No Vexa port is published | `docker compose --profile vexa ps` shows no host port for `vexa*` | |
| Frontend loads | open `http://localhost:3000` | |

## 2. Capture

1. Create a Meet and join as the participant (a second browser profile or a colleague).
2. In Baraza open `http://localhost:3000/meetings/new`. Enter a title and the Meet link, tick the
   consent box, start.
3. In the call, **admit** the participant named `Baraza – note taker`.
4. Speak for two minutes with at least two voices. Say clearly:
   - one decision ("We agree to hold the review on 20 November"),
   - one action with a named owner and a deadline,
   - one action with **no** owner and **no** deadline,
   - one thing that is **not** said, to check nothing is invented (for example do not mention a
     budget at all).
5. Stop from Baraza (not by closing the call).

| Criterion | What to see | Result |
|---|---|---|
| Consent required | Start is impossible without the consent box | |
| Status is visible | The meeting page shows waiting for admission, then capturing | |
| The bot is clearly named | The tile reads `Baraza – note taker`, it is visible to everyone | |
| The bot announces itself | A message in the Meet chat says it is an assistant that transcribes | |
| Not admitted case | (optional) deny the bot once: Baraza shows a clear failure, nothing is recorded | |
| Stop works | After Stop, the page moves to processing, then done | |
| Segments are stored | `curl -s localhost:8000/meetings/<id>/segments` returns timestamped lines | |

## 3. Minutes

| Criterion | What to see | Result |
|---|---|---|
| A draft is generated | The page shows a summary, decisions and actions | |
| The decision is right | It matches what was said | |
| The owned action keeps its owner and deadline | | |
| The other action has no owner and no deadline | It shows "Not specified", nothing invented | |
| Nothing was invented | No budget, person or date that nobody said | |
| Corrections are visible | `curl -s localhost:8000/meetings/<id>/minutes/meta` lists any removed or nulled items | |
| Draft after a refresh | Reload the page: transcript and draft are still there | |

## 4. Review and history

Replace `<id>` with the meeting id.

```bash
curl -s localhost:8000/meetings
curl -s -i localhost:8000/meetings/<id>/minutes          # read the ETag
curl -s -X PUT localhost:8000/meetings/<id>/minutes \
  -H "Content-Type: application/json" -H 'If-Match: "1"' -d @edited-minutes.json
curl -s -X POST localhost:8000/meetings/<id>/minutes/validate -H 'If-Match: "2"'
curl -s localhost:8000/meetings/<id>/minutes/revisions
```

| Criterion | What to see | Result |
|---|---|---|
| The meeting is in the history | `GET /meetings` lists it, `needs_review` is true for the draft | |
| An edit is saved | The version goes from 1 to 2 | |
| A stale edit is refused | Re-send with `If-Match: "1"`: status 412 | |
| Validation locks the minutes | A later `PUT` returns 409 | |
| The original is kept | `/revisions/1` is the assistant's text | |

There is no user sign in yet: every action is attributed to `local-user`. Record that as a known
gap, not as a pass.

## 5. Failure and recovery

| Criterion | What to see | Result |
|---|---|---|
| Model down | `docker compose stop ollama`, generate again: the page shows a clear failure with retry | |
| Retry works | `docker compose start ollama`, press retry: a draft appears | |
| API restart mid-call | During a second capture, `docker compose restart api`: status and stop still work | |
| Worker restart mid-call | `docker compose restart worker` during a capture: the capture completes | |

## 6. If the real capture fails

Do not hide it. Record the failing step and the output of
`docker compose logs --tail 100 api worker vexa`, then run the rehearsal in
[sprint-3-demo.md](sprint-3-demo.md) with `BARAZA_CAPTURE_MODE=fake`. That rehearsal must be
presented as a simulation, never as a live capture.

## 7. Result

| | |
|---|---|
| Date and people | |
| Commit tested | `git rev-parse --short HEAD` |
| Model used | |
| Blocking problems found | |
| Minor problems found | |
| Verdict | Passed / Passed with known gaps / Failed |
