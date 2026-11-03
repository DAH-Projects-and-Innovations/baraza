"""Tâche arq generate_minutes_task et branchement de démarrage."""
import pytest

from baraza import worker
from baraza.llm.client import FakeLLMClient
from baraza.llm.resilient import ResilientLLMClient
from baraza.storage.minutes_sql import SqlMinutesRepository
from minutes_fakes import MemRepo, Notifier
from test_minutes_pipeline import ANSWER, transcript


@pytest.mark.asyncio
async def test_task_returns_a_serializable_summary():
    ctx = {"repo": MemRepo(transcript()), "llm": FakeLLMClient(ANSWER), "notifier": Notifier()}
    out = await worker.generate_minutes_task(ctx, "m1")
    assert out["status"] == "draft_ready" and out["draft_id"] == 1 and out["error_code"] is None
    assert out["corrections"] == ["item_rejected:1", "owner_nulled:1"]


@pytest.mark.asyncio
async def test_task_is_registered_and_arq_retries_unexpected_errors():
    assert worker.generate_minutes_task in worker.WorkerSettings.functions
    assert worker.WorkerSettings.max_tries == 3


@pytest.mark.asyncio
async def test_startup_builds_llm_repo_notifier_and_shutdown_disposes(monkeypatch, tmp_path):
    class S:
        llm_base_url, llm_model, llm_api_key = "http://x/v1", "m", "k"
        database_url = f"sqlite+aiosqlite:///{tmp_path}/w.db"

    monkeypatch.setattr(worker, "get_settings", lambda: S())
    ctx = {}
    await worker.startup(ctx)
    assert isinstance(ctx["llm"], ResilientLLMClient) and isinstance(ctx["repo"], SqlMinutesRepository)
    assert ctx["notifier"] is not None
    await worker.shutdown(ctx)
