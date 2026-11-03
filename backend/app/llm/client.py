"""Client LLM résilient, API compatible OpenAI (issues #81 et #82).

Fonctionne avec LiteLLM, Ollama (/v1), vLLM, OpenAI... : seule la config change.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

import httpx

from .errors import (
    ContextTooLongError,
    LLMAuthError,
    LLMError,
    LLMServerError,
    LLMTimeoutError,
    ModelUnreachableError,
    OutputTruncatedError,
    QuotaExceededError,
    ResponseFormatUnsupportedError,
)

logger = logging.getLogger(__name__)

_CONTEXT_MARKERS = (
    "context_length",
    "context length",
    "maximum context",
    "context window",
    "prompt is too long",
    "too many tokens",
)
_FORMAT_MARKERS = ("response_format", "json_schema", "json_object", "structured output")

# Formats de sortie, du plus strict au plus permissif.
FORMAT_SCHEMA, FORMAT_OBJECT, FORMAT_NONE = "json_schema", "json_object", "none"


@dataclass(frozen=True)
class LLMSettings:
    base_url: str  # ex: http://localhost:11434/v1
    model: str
    api_key: str | None = None
    timeout_s: float = 60.0
    max_output_tokens: int = 2048
    max_retries: int = 3  # nombre de RE-tentatives (donc 4 appels max)
    backoff_base_s: float = 1.0
    backoff_max_s: float = 30.0
    jitter: bool = True
    # "auto" : json_schema -> json_object -> aucun, selon ce que le fournisseur accepte.
    # Les autres valeurs forcent un format ("none" = prompt seul, pour les modèles capricieux).
    structured_output: Literal["auto", "json_schema", "json_object", "none"] = "auto"
    # Flag de debug : seul moyen de logger prompts/réponses. DOIT rester False en prod.
    debug_log_content: bool = False


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.settings = settings
        self._transport = transport
        self._sleep = sleep
        self._unsupported_formats: set[str] = set()  # mémorise les refus du fournisseur
        self.last_response_format: str | None = None  # utile pour les tests réels

    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        json_schema: dict | None = None,
    ) -> str:
        """json_schema (si fourni) implique une sortie structurée ; json_mode seul = json_object."""
        s = self.settings
        base = {
            "model": s.model,
            "messages": messages,
            "max_tokens": s.max_output_tokens,
            "temperature": 0,
        }
        candidates = self._candidate_formats(json_mode, json_schema)
        usable = [f for f in candidates if f not in self._unsupported_formats] or candidates

        last_error: LLMError | None = None
        for fmt in usable:
            payload = dict(base)
            response_format = self._response_format(fmt, json_schema)
            if response_format:
                payload["response_format"] = response_format
            try:
                text = await self._send_with_retries(payload)
            except ResponseFormatUnsupportedError as exc:
                logger.info("llm response_format=%s refusé, format suivant", fmt)
                self._unsupported_formats.add(fmt)
                last_error = exc
                continue
            self.last_response_format = fmt
            return text

        assert last_error is not None
        raise last_error

    # --- choix du format de sortie (#82) -----------------------------------------

    def _candidate_formats(self, json_mode: bool, json_schema: dict | None) -> list[str]:
        mode = self.settings.structured_output
        if mode == "none" or (not json_mode and json_schema is None):
            return [FORMAT_NONE]
        if mode == FORMAT_SCHEMA:
            return [FORMAT_SCHEMA] if json_schema else [FORMAT_OBJECT]
        if mode == FORMAT_OBJECT:
            return [FORMAT_OBJECT]
        return ([FORMAT_SCHEMA] if json_schema else []) + [FORMAT_OBJECT, FORMAT_NONE]

    @staticmethod
    def _response_format(fmt: str, json_schema: dict | None) -> dict | None:
        if fmt == FORMAT_SCHEMA:
            return {
                "type": "json_schema",
                "json_schema": {"name": "meeting_minutes", "strict": False, "schema": json_schema},
            }
        if fmt == FORMAT_OBJECT:
            return {"type": "json_object"}
        return None

    # --- appel HTTP avec retries (#81) --------------------------------------------

    async def _send_with_retries(self, payload: dict) -> str:
        s = self.settings
        headers = {"Authorization": f"Bearer {s.api_key}"} if s.api_key else {}
        url = s.base_url.rstrip("/") + "/chat/completions"

        if s.debug_log_content:
            logger.debug("LLM request: %s", payload)

        last_error: LLMError | None = None
        retry_after: float | None = None
        for attempt in range(s.max_retries + 1):
            started = time.monotonic()
            retry_after = None
            try:
                async with httpx.AsyncClient(
                    timeout=s.timeout_s, transport=self._transport
                ) as http:
                    resp = await http.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                last_error = LLMTimeoutError()
            except httpx.TransportError:
                last_error = ModelUnreachableError()
            else:
                # Métadonnées seulement : jamais le contenu.
                logger.info(
                    "llm call model=%s attempt=%d status=%d duration=%.2fs",
                    s.model, attempt, resp.status_code, time.monotonic() - started,
                )
                if resp.status_code == 200:
                    return self._extract(resp)
                error, retryable = self._map_http_error(resp)
                if not retryable:
                    raise error
                last_error = error
                retry_after = self._parse_retry_after(resp)

            if attempt == s.max_retries:
                break
            await self._sleep(self._delay(attempt, retry_after))

        assert last_error is not None
        raise last_error

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        s = self.settings
        if retry_after is not None:
            return min(retry_after, s.backoff_max_s)
        delay = min(s.backoff_max_s, s.backoff_base_s * (2**attempt))
        return delay * random.uniform(0.5, 1.0) if s.jitter else delay

    @staticmethod
    def _parse_retry_after(resp: httpx.Response) -> float | None:
        value = resp.headers.get("retry-after")
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _map_http_error(resp: httpx.Response) -> tuple[LLMError, bool]:
        """Retourne (erreur, retryable)."""
        status = resp.status_code
        body = resp.text.lower()
        if status in (400, 413, 422) and any(m in body for m in _CONTEXT_MARKERS):
            return ContextTooLongError(), False
        if status in (400, 422) and any(m in body for m in _FORMAT_MARKERS):
            return ResponseFormatUnsupportedError(), False
        if status == 429:
            if "insufficient_quota" in body or "billing" in body:
                return QuotaExceededError(), False  # inutile de réessayer
            return QuotaExceededError("rate limited"), True
        if status in (401, 403):
            return LLMAuthError(), False
        if status >= 500:
            return LLMServerError(f"HTTP {status}"), True
        return LLMError(f"HTTP {status}"), False

    def _extract(self, resp: httpx.Response) -> str:
        try:
            choice = resp.json()["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMError("Réponse du fournisseur illisible") from exc
        if self.settings.debug_log_content:
            logger.debug("LLM response: %s", content)
        if choice.get("finish_reason") == "length":
            raise OutputTruncatedError()
        return content or ""
