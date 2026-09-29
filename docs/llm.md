# Choosing the language model

The core calls an OpenAI-compatible API. The model is chosen only through environment variables
(see `.env.example`):

| Variable | Role |
|---|---|
| `BARAZA_LLM_BASE_URL` | API URL (LiteLLM, Ollama, vLLM, hosted provider) |
| `BARAZA_LLM_API_KEY` | API key (ignored by Ollama) |
| `BARAZA_LLM_MODEL` | Model name |
| `BARAZA_LLM_IS_EXTERNAL` | `true` if data leaves your infrastructure |

## Examples

```bash
# Local Ollama (docker compose "local" profile)
BARAZA_LLM_BASE_URL=http://ollama:11434/v1
BARAZA_LLM_MODEL=mistral

# LiteLLM gateway
BARAZA_LLM_BASE_URL=http://litellm:4000/v1
BARAZA_LLM_MODEL=mistral-large
BARAZA_LLM_IS_EXTERNAL=true
```

## Prompts

Prompts are versioned in `backend/src/baraza/prompts/<language>/`, one folder per output language.
The model must return JSON matching the `Minutes` schema (`backend/src/baraza/core/minutes.py`);
any invalid response is rejected.

## Model comparison

To be completed during the proof of concept, using the evaluation set (`eval/`).
