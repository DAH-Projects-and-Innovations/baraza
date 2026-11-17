# Baraza – backend

Application core (Python, FastAPI, arq). See the [main README](../README.md).

```bash
uv sync                                        # install dependencies
uv run alembic upgrade head                     # apply schema before API/worker startup
uv run fastapi dev src/baraza/main.py          # API on http://localhost:8000
uv run arq baraza.worker.WorkerSettings        # worker (requires Redis)
uv run pytest -m 'not integration'              # tests without Postgres/Redis
uv run ruff check . && uv run ruff format .    # lint and format
uv run mypy src                                # type checking
```

Configure `BARAZA_DATABASE_URL` before running migrations. Compose runs its one-shot
`migrate` service before starting API and worker. See the
[Sprint 04 database guide](../docs/sprint04-thierry.md) for migration authoring,
real Postgres/Redis integration tests, and versioned minutes.

## Layout

```
src/baraza/
├── main.py            # FastAPI application
├── config.py          # configuration (BARAZA_* variables)
├── db/                # shared metadata, async engine and session dependency
├── api/               # HTTP routes
├── core/              # common transcript format, minutes schema, generation
├── adapters/          # capture adapter contract + implementations
├── llm/               # OpenAI-compatible client + fake model
├── prompts/           # versioned prompts, one folder per language
└── worker.py          # background tasks
```

## Optional Vexa backend

See [Vexa setup, polling, meeting states and validation](../docs/vexa-backend.md)
for issues #124–#128 and #77.
