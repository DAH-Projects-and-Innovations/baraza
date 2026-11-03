"""Background task worker (arq + Redis).

Run with: ``uv run arq baraza.worker.WorkerSettings``
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from baraza.adapters.base import CaptureStatus
from baraza.api.dependencies import get_meeting_store
from baraza.config import get_settings
from baraza.core.generation import generate_minutes
from baraza.llm.client import OpenAICompatibleClient


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
        llm = ctx.get("llm") or OpenAICompatibleClient(get_settings())
        minutes = await generate_minutes(meeting.transcript, llm)
        references = (
            [topic.source for topic in minutes.topics]
            + [decision.source for decision in minutes.decisions]
            + [action.source for action in minutes.actions]
            + [point.source for point in minutes.open_points]
        )
        if any(
            index < 0 or index >= len(meeting.transcript.segments)
            for source in references
            for index in source.segment_indices
        ):
            raise ValueError("Draft refers to a segment outside the transcript")
        meeting.minutes = minutes
        meeting.status = CaptureStatus.DONE
        meeting.error = None
    except Exception:
        # No model response or transcript text in logs or user-facing errors.
        meeting.status = CaptureStatus.FAILED
        meeting.error = "Draft generation failed. Check the model service, then retry."
    await store.save(meeting)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [generate_minutes_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
    keep_result = 0
