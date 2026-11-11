"""Background task worker (arq + Redis).

Run with: ``uv run arq baraza.worker.WorkerSettings``
"""

from typing import Any, ClassVar

import httpx
import structlog
from arq import cron
from arq.connections import RedisSettings
from arq.worker import func

from baraza.adapters.base import CaptureStatus
from baraza.adapters.vexa import VexaAdapter
from baraza.api.dependencies import get_meeting_store
from baraza.config import get_settings
from baraza.core.captures import VexaCaptureService
from baraza.core.pipeline import generate_checked_minutes
from baraza.db.session import Database
from baraza.llm.resilient import ResilientLLMClient
from baraza.storage.captures import SqlCaptureStore
from baraza.storage.sql import SqlSegmentStore
from baraza.vexa.client import VexaClient


async def generate_minutes_task(ctx: dict[str, Any], meeting_id: str) -> None:
    store = ctx.get("meeting_store") or get_meeting_store()
    meeting = await store.get(meeting_id)
    if meeting is None or meeting.status != CaptureStatus.PROCESSING:
        return
    if meeting.transcript is None:
        meeting.status = CaptureStatus.FAILED
        meeting.error = "No validated transcript is available."
        await store.save(meeting)
        return
    try:
        llm = ctx.get("llm") or ResilientLLMClient.from_settings(get_settings())
        # Out-of-range sources, unsupported owners and unsupported deadlines are removed and
        # traced in ``corrections`` rather than shown as facts.
        minutes, corrections, prompt_version = await generate_checked_minutes(
            meeting.transcript, llm, meeting_date=meeting.started_at.date()
        )
        meeting.minutes = minutes
        meeting.corrections = corrections
        meeting.prompt_version = prompt_version
        meeting.status = CaptureStatus.DONE
        meeting.error = None
    except Exception:
        # No model response or transcript text in logs or user-facing errors.
        meeting.status = CaptureStatus.FAILED
        meeting.error = "Draft generation failed. Check the model service, then retry."
    await store.save(meeting)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    ctx["database"] = database
    if not settings.vexa_enabled:
        return
    try:
        client = VexaClient(settings)
    except Exception:
        await database.dispose()
        ctx.pop("database")
        raise
    engine = database.engine
    ctx["vexa_engine"] = engine
    ctx["vexa_client"] = client
    ctx["vexa_service"] = VexaCaptureService(
        VexaAdapter(client, settings),
        SqlCaptureStore(engine),
        SqlSegmentStore(engine),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    try:
        if "vexa_client" in ctx:
            await ctx["vexa_client"].aclose()
    finally:
        if "database" in ctx:
            await ctx["database"].dispose()


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
    keep_result = 0
