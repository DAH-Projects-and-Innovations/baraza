"""Replaceable integration ports for capture, persistence and job submission."""

from functools import lru_cache

from arq.connections import RedisSettings, create_pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from baraza.adapters.base import CaptureAdapter
from baraza.adapters.fake import FakeCaptureAdapter
from baraza.adapters.vexa import VexaAdapter
from baraza.config import get_settings
from baraza.storage.sql import SqlMeetingStore
from baraza.vexa.client import VexaClient


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url)


@lru_cache
def get_meeting_store() -> SqlMeetingStore:
    return SqlMeetingStore(get_engine())


@lru_cache
def get_capture_adapter() -> CaptureAdapter | None:
    settings = get_settings()
    if settings.capture_mode == "fake":
        return FakeCaptureAdapter()
    if settings.capture_mode == "vexa" and settings.vexa_api_key.get_secret_value():
        return VexaAdapter(VexaClient(settings), settings)
    # "disabled", or "vexa" without an API key: the API answers 503 instead of guessing.
    return None


async def close_capture_adapter() -> None:
    """Release the Vexa HTTP client at shutdown, if one was created."""
    if get_capture_adapter.cache_info().currsize:
        adapter = get_capture_adapter()
        if isinstance(adapter, VexaAdapter):
            await adapter.client.aclose()
        get_capture_adapter.cache_clear()


class GenerationQueue:
    async def enqueue(self, meeting_id: str) -> None:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        try:
            # One active generation job per meeting, including repeated stop requests.
            await pool.enqueue_job(
                "generate_minutes_task",
                meeting_id,
                _job_id=f"minutes:{meeting_id}",
            )
        finally:
            await pool.aclose()


def get_generation_queue() -> GenerationQueue:
    return GenerationQueue()
