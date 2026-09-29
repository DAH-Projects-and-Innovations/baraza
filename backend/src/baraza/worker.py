"""Background task worker (arq + Redis).

Run with: ``uv run arq baraza.worker.WorkerSettings``
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from baraza.config import get_settings


async def generate_minutes_task(ctx: dict[str, Any], meeting_id: str) -> None:
    # TODO: load the transcript, call generate_minutes, store the draft, notify the organizer.
    raise NotImplementedError


class WorkerSettings:
    functions: ClassVar[list[Any]] = [generate_minutes_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
