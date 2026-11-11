"""Background task worker (arq + Redis).

Run with: ``uv run arq baraza.worker.WorkerSettings``
"""

from typing import Any, ClassVar

import httpx
import structlog
from arq import cron
from arq.connections import RedisSettings
from arq.worker import func
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.adapters.vexa import VexaAdapter
from baraza.config import get_settings
from baraza.core.captures import VexaCaptureService
from baraza.storage.captures import SqlCaptureStore
from baraza.storage.sql import SqlSegmentStore
from baraza.vexa.client import VexaClient


async def generate_minutes_task(ctx: dict[str, Any], meeting_id: str) -> None:
    # TODO: load the transcript, call generate_minutes, store the draft, notify the organizer.
    raise NotImplementedError


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.vexa_enabled:
        return
    engine = create_async_engine(settings.database_url)
    client = VexaClient(settings)
    ctx["vexa_engine"] = engine
    ctx["vexa_client"] = client
    ctx["vexa_service"] = VexaCaptureService(
        VexaAdapter(client, settings),
        SqlCaptureStore(engine),
        SqlSegmentStore(engine),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    if "vexa_client" in ctx:
        await ctx["vexa_client"].aclose()
        await ctx["vexa_engine"].dispose()


async def start_vexa_capture_task(
    ctx: dict[str, Any],
    meeting_id: str,
    meeting_url: str,
) -> str:
    service: VexaCaptureService = ctx["vexa_service"]
    return await service.start(meeting_id, meeting_url)


async def stop_vexa_capture_task(ctx: dict[str, Any], meeting_id: str) -> None:
    service: VexaCaptureService = ctx["vexa_service"]
    await service.stop(meeting_id)


async def enqueue_vexa_poll(ctx: dict[str, Any]) -> None:
    if "vexa_service" in ctx:
        # Normal jobs release their in-progress marker immediately; ARQ cron keeps it for 60s.
        await ctx["redis"].enqueue_job("poll_vexa_captures", _job_id="vexa-status-poll")


async def poll_vexa_captures(ctx: dict[str, Any]) -> None:
    service: VexaCaptureService | None = ctx.get("vexa_service")
    if service is None:
        return
    for capture in await service.captures.captures():
        try:
            await service.poll(capture)
        except httpx.HTTPError:
            # Keep the handle active: network/auth errors are not proof the meeting failed.
            structlog.get_logger().warning("vexa_poll_http_error", meeting_id=capture.meeting_id)
        except ValueError:
            # Malformed/mismatched data must never finish a capture or ingest another meeting.
            structlog.get_logger().warning("vexa_poll_invalid_data", meeting_id=capture.meeting_id)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        generate_minutes_task,
        func(start_vexa_capture_task, max_tries=1),
        stop_vexa_capture_task,
        func(poll_vexa_captures, keep_result=0, max_tries=1),
    ]
    on_startup = startup
    on_shutdown = shutdown
    # Dispatch a normal job with a stable id, preventing overlapping sweeps across workers.
    cron_jobs: ClassVar[list[Any]] = [
        cron(
            enqueue_vexa_poll,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            keep_result=0,
        )
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
