"""Small client for the Vexa v0.12.26 gateway (X-API-Key authentication)."""

import asyncio
from datetime import datetime
from typing import Any, Literal, Self
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, model_validator

from baraza.config import Settings

Platform = Literal["google_meet", "teams", "zoom"]
BotState = Literal[
    "idle",
    "scheduled",
    "requested",
    "joining",
    "awaiting_admission",
    "needs_help",
    "active",
    "stopping",
    "completed",
    "failed",
]


class BotRequest(BaseModel):
    platform: Platform
    native_meeting_id: str = Field(min_length=1)
    bot_name: str = Field(min_length=1)
    meeting_url: str
    transcribe_enabled: bool = True
    recording_enabled: bool = False


class BotResponse(BaseModel):
    id: int | str
    platform: Platform
    native_meeting_id: str
    status: BotState
    start_time: datetime | None = None
    end_time: datetime | None = None


class StopResponse(BaseModel):
    status: Literal["stopping"]
    meeting_id: int | str


class VexaSegment(BaseModel):
    segment_id: str = Field(min_length=1)
    speaker: str | None = None
    speaker_id: str | None = None
    text: str = Field(min_length=1)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(ge=0, allow_inf_nan=False)
    language: str | None = None
    completed: bool = True

    @model_validator(mode="after")
    def valid_interval(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class TranscriptResponse(BotResponse):
    segments: list[VexaSegment]


class VexaClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not settings.vexa_api_key.get_secret_value():
            raise ValueError("BARAZA_VEXA_API_KEY must be configured")
        self._http = httpx.AsyncClient(
            base_url=settings.vexa_base_url.rstrip("/") + "/",
            headers={"X-API-Key": settings.vexa_api_key.get_secret_value()},
            timeout=httpx.Timeout(settings.vexa_timeout_seconds),
            transport=transport,
            follow_redirects=False,
        )
        self._retries = settings.vexa_retries

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        # Never retry POST /bots: after an ambiguous timeout it could spawn a second bot.
        retries = self._retries if method in {"GET", "DELETE"} else 0
        for attempt in range(retries + 1):
            try:
                response = await self._http.request(method, path, **kwargs)
                if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt == retries:
                    response.raise_for_status()
                    return response
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries:
                    raise
            await asyncio.sleep(min(0.25 * 2**attempt, 2))
        raise AssertionError("unreachable")

    async def request_bot(self, request: BotRequest) -> BotResponse:
        response = await self._request("POST", "bots", json=request.model_dump())
        return BotResponse.model_validate(response.json())

    async def stop_bot(self, platform: Platform, native_id: str) -> StopResponse:
        response = await self._request("DELETE", f"bots/{platform}/{quote(native_id, safe='')}")
        return StopResponse.model_validate(response.json())

    async def get_bot(self, bot_id: str) -> BotResponse:
        response = await self._request("GET", f"meetings/{quote(bot_id, safe='')}")
        return BotResponse.model_validate(response.json())

    async def get_transcript(self, bot_id: str) -> TranscriptResponse:
        # By record id, so reusing a Meet link cannot retrieve a different occurrence.
        response = await self._request("GET", f"transcripts/by-id/{quote(bot_id, safe='')}")
        return TranscriptResponse.model_validate(response.json())
