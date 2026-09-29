# Baraza – backend

Application core (Python, FastAPI, arq). See the [main README](../README.md).

```bash
uv sync                                        # install dependencies
uv run fastapi dev src/baraza/main.py          # API on http://localhost:8000
uv run arq baraza.worker.WorkerSettings        # worker (requires Redis)
uv run pytest                                  # tests (fake model, no network)
uv run ruff check . && uv run ruff format .    # lint and format
uv run mypy src                                # type checking
```

## Layout

```
src/baraza/
├── main.py            # FastAPI application
├── config.py          # configuration (BARAZA_* variables)
├── api/               # HTTP routes
├── core/              # common transcript format, minutes schema, generation
├── adapters/          # capture adapter contract + implementations
├── llm/               # OpenAI-compatible client + fake model
├── prompts/           # versioned prompts, one folder per language
└── worker.py          # background tasks
```
