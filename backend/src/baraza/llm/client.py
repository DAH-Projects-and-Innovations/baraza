"""Language model access through an OpenAI-compatible API.

The model is chosen through configuration (``BARAZA_LLM_*``), never in code.
"""

from typing import Protocol

from openai import AsyncOpenAI

from baraza.config import Settings


class LLMClient(Protocol):
    async def complete_json(self, system: str, user: str) -> str:
        """Return the raw model response, expected to be JSON."""
        ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
        self._model = settings.llm_model

    async def complete_json(self, system: str, user: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return response.choices[0].message.content or ""


class FakeLLMClient:
    """Fake model for tests: returns a predefined response."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def complete_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response
