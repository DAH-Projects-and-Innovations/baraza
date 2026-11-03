"""Background task worker (arq + Redis).

Run with: ``uv run arq baraza.worker.WorkerSettings``
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from baraza.config import get_settings
from baraza.core.pipeline import LogNotifier, run_generation
from baraza.llm.resilient import ResilientLLMClient
from baraza.storage.minutes_sql import SqlMinutesRepository, engine_from_settings


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["llm"] = ResilientLLMClient.from_settings(settings)
    ctx["engine"] = engine_from_settings(settings)
    ctx["repo"] = SqlMinutesRepository(ctx["engine"])
    ctx["notifier"] = LogNotifier()  # TODO: notifier réel (organisateur de la réunion)


async def shutdown(ctx: dict[str, Any]) -> None:
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


async def generate_minutes_task(
    ctx: dict[str, Any], meeting_id: str, force: bool = False
) -> dict[str, Any]:
    """Charge la transcription, génère le brouillon, applique les contrôles, le stocke, notifie.

    Les échecs attendus (modèle, JSON invalide, transcription vide) sont enregistrés avec un
    message lisible et ne sont pas relancés ; les erreurs inattendues sont relancées pour qu'arq
    réessaie (max_tries).
    """
    result = await run_generation(
        meeting_id, repo=ctx["repo"], llm=ctx["llm"], notifier=ctx["notifier"], force=force
    )
    return {
        "status": result.status,
        "draft_id": result.draft_id,
        "error_code": result.error_code,
        "corrections": list(result.corrections),
    }


class WorkerSettings:
    functions: ClassVar[list[Any]] = [generate_minutes_task]
    on_startup: ClassVar[Any] = startup
    on_shutdown: ClassVar[Any] = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
