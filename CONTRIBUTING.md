# Contributing to Baraza

Thanks for your interest! All contributions are welcome: code, documentation, adapters, evaluation
data, bug reports.

## Before you start

- Read the [code of conduct](CODE_OF_CONDUCT.md).
- For a new feature, open an issue first to discuss it.
- Issues labeled `good first issue` are a good starting point.
- To write an adapter, read [docs/adapters.md](docs/adapters.md).
- Everything in the repository (code, comments, docs, commits, issues) is written in English.

## Setup

```bash
# Backend (Python 3.12, uv)
cd backend
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src

# Frontend (Node 24, pnpm)
cd frontend
pnpm install
pnpm lint && pnpm typecheck && pnpm build
```

Pre-commit hooks (recommended):

```bash
uvx pre-commit install
```

## Branches and pull requests

- `main`: released version. `development`: integration branch.
- Branch off `development`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat: …`, `fix: …`, `docs: …`).
- A review is required before any merge, and CI must pass.
- Update `CHANGELOG.md` ("Unreleased" section) for any user-visible change.

## Mandatory rules

- **No real data** (transcripts, recordings, names, emails) in the repository or its Git history.
  Test data is fictional.
- **No secrets**: keys and tokens go through environment variables.
- **Core tests never call a video conferencing platform or a real model**: use `FakeLLMClient`.
- Any new dependency must have an Apache-2.0-compatible license (no "source-available" licenses
  such as the Elastic License 2.0).
