# Baraza

> Open source tool that automatically produces the minutes of your online meetings, from their
> transcript and the language model of your choice.

**Status: under development (scoping / proof of concept).** Not ready for production use yet.

Baraza does not reinvent video conferencing, meeting bots or transcription: it builds on existing
open source components. Its own value is the pipeline from transcript to validated minutes:
structuring, decisions, action items, follow-up, export.

- **Platforms**: Google Meet at launch, then Teams and Zoom through adapters.
- **Pluggable language model**: local (Ollama, vLLM), private cloud or hosted provider, by
  configuration only.
- **Private by default**: a fully local deployment is possible, with no outbound calls.
- **Humans validate**: no minutes are shared without review; the system never invents a decision,
  an owner or a due date.

## Quick start

Requirements: Docker and Docker Compose.

```bash
cp .env.example .env
docker compose up                   # external language model configured in .env
docker compose --profile local up   # fully local, with Ollama
```

- Web interface: http://localhost:3000
- API: http://localhost:8000 (interactive docs at `/docs`)

With the `local` profile, pull a model on first run:

```bash
docker compose exec ollama ollama pull mistral
```

## Development

| Part | Folder | Tooling |
|---|---|---|
| Core and API | [`backend/`](backend/) | Python 3.12, [uv](https://docs.astral.sh/uv/), FastAPI, arq |
| Web interface | [`frontend/`](frontend/) | Node 24, pnpm, Next.js, Tailwind CSS |
| Evaluation set | [`eval/`](eval/) | Fictional meetings |
| Documentation | [`docs/`](docs/) | Architecture, adapters, models, GDPR |

```bash
# Backend
cd backend && uv sync && uv run pytest

# Frontend
cd frontend && pnpm install && pnpm dev
```

To run only the infrastructure services locally: `docker compose up postgres redis`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions.

## Architecture

```
Capture adapters        ──►  Core                ──►  Outputs
(native Meet, Vexa bot,      common format,           web interface,
 file import…)               minutes generation,      Word/PDF/Markdown export
                             validation, follow-up
                                   ▲
                                   │ OpenAI-compatible API
                             LLM gateway (LiteLLM, Ollama, vLLM…)
```

Details in [docs/architecture.md](docs/architecture.md).

## License

[Apache-2.0](LICENSE).
