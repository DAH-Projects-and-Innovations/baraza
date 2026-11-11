"""Exposition du compte rendu : statut + dernier brouillon, et déclenchement de la génération."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any, Literal

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from baraza.config import get_settings
from baraza.core.minutes import Minutes
from baraza.core.pipeline import STATUS_NOT_STARTED
from baraza.storage.minutes_sql import SqlMinutesRepository, engine_from_settings

router = APIRouter(prefix="/meetings", tags=["minutes"])


class DraftOut(BaseModel):
    id: int
    created_at: datetime | None = None
    model: str
    prompt_version: str
    # Un champ None doit être affiché « Non précisé » / « Not specified » par l'interface.
    minutes: Minutes
    corrections: list[dict[str, Any]]  # ce que les contrôles anti-invention ont modifié


class MinutesOut(BaseModel):
    meeting_id: str
    status: str  # not_started | generating | draft_ready | generation_failed
    reason: str | None = None
    draft: DraftOut | None = None


class QueuedOut(BaseModel):
    meeting_id: str
    status: Literal["queued"] = "queued"


@lru_cache
def get_repo() -> SqlMinutesRepository:
    return SqlMinutesRepository(engine_from_settings(get_settings()))


_pool: Any = None


async def get_queue() -> Any:
    """File arq (Redis). Remplacée par un faux dans les tests (dependency_overrides)."""
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


@router.get("/{meeting_id}/minutes", response_model=MinutesOut)
async def read_minutes(
    meeting_id: str, repo: Annotated[SqlMinutesRepository, Depends(get_repo)]
) -> MinutesOut:
    """Interrogeable en boucle par l'interface (polling) : ne renvoie jamais 404."""
    state = await repo.get_state(meeting_id)
    draft = await repo.get_latest_draft(meeting_id)
    status, reason = state if state else (STATUS_NOT_STARTED, None)
    return MinutesOut(
        meeting_id=meeting_id,
        status=status,
        reason=reason,
        draft=DraftOut(**draft) if draft else None,
    )


@router.post("/{meeting_id}/generate", status_code=202, response_model=QueuedOut)
async def generate(
    meeting_id: str, queue: Annotated[Any, Depends(get_queue)], force: bool = False
) -> QueuedOut:
    """Déclenche la génération (à la main, ou en secours si le déclenchement auto échoue)."""
    await queue.enqueue_job("generate_minutes_task", meeting_id, force)
    return QueuedOut(meeting_id=meeting_id)
