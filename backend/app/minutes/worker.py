"""Branchement dans le worker arq (issue #89).

Dans le module worker EXISTANT du projet :

    from app.minutes.worker import generate_minutes_job, startup_llm

    class WorkerSettings:
        functions = [..., generate_minutes_job]
        async def on_startup(ctx):
            await startup_llm(ctx)                 # crée ctx["llm"] depuis le .env
            ctx["repo"] = MonRepository(...)       # implémentation réelle de MeetingRepository
            ctx["notifier"] = MonNotifier(...)     # implémentation réelle de Notifier

Pour déclencher la génération (à la fin de l'ingestion, issue #78) :

    await redis.enqueue_job("generate_minutes_job", meeting_id)
"""
from __future__ import annotations

from app.llm.client import LLMClient
from app.llm.config import load_llm_settings

from .generation import run_generation


async def startup_llm(ctx: dict) -> None:
    ctx["llm"] = LLMClient(load_llm_settings())


async def generate_minutes_job(ctx: dict, meeting_id: str, force: bool = False) -> dict:
    result = await run_generation(
        meeting_id, repo=ctx["repo"], client=ctx["llm"], notifier=ctx["notifier"], force=force
    )
    return {"status": result.status, "draft_id": result.draft_id, "error_code": result.error_code}
