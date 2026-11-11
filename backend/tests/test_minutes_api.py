"""Routes GET /meetings/{id}/minutes et POST /meetings/{id}/generate."""

import httpx
import pytest
import pytest_asyncio
from baraza.storage.sql import SqlSegmentStore
from minutes_fakes import Notifier
from sqlalchemy.ext.asyncio import create_async_engine
from test_minutes_pipeline import ANSWER, SEGMENTS, Scripted

from baraza.api import minutes as api
from baraza.core.pipeline import run_generation
from baraza.main import create_app
from baraza.storage.minutes_sql import SqlMinutesRepository


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, name, *args):
        self.jobs.append((name, args))


@pytest_asyncio.fixture
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/api.db")
    repo, queue, app = SqlMinutesRepository(engine), FakeQueue(), create_app()
    app.dependency_overrides[api.get_repo] = lambda: repo
    app.dependency_overrides[api.get_queue] = lambda: queue
    await SqlSegmentStore(engine).upsert(SEGMENTS)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        c.repo, c.queue = repo, queue
        yield c
    await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_meeting_is_not_started_not_404(client):
    r = await client.get("/meetings/inconnue/minutes")
    assert r.status_code == 200
    assert r.json() == {
        "meeting_id": "inconnue",
        "status": "not_started",
        "reason": None,
        "draft": None,
    }


@pytest.mark.asyncio
async def test_generate_enqueues_the_worker_task(client):
    r = await client.post("/meetings/m1/generate")
    assert r.status_code == 202 and r.json() == {"meeting_id": "m1", "status": "queued"}
    assert client.queue.jobs == [("generate_minutes_task", ("m1", False))]
    await client.post("/meetings/m1/generate?force=true")
    assert client.queue.jobs[-1] == ("generate_minutes_task", ("m1", True))


@pytest.mark.asyncio
async def test_draft_ready_returns_minutes_and_corrections(client):
    await run_generation("m1", repo=client.repo, llm=Scripted(ANSWER), notifier=Notifier())
    body = (await client.get("/meetings/m1/minutes")).json()
    assert body["status"] == "draft_ready" and body["reason"] is None
    d = body["draft"]
    assert d["minutes"]["summary"] == "Bêta validée." and d["model"] == "scripted-model"
    assert d["minutes"]["actions"][1]["owner"] is None  # null : à afficher « Non précisé »
    assert {c["kind"] for c in d["corrections"]} == {"item_rejected", "owner_nulled"}


@pytest.mark.asyncio
async def test_failed_generation_exposes_a_readable_reason(client):
    await run_generation("m1", repo=client.repo, llm=Scripted("pas du json"), notifier=Notifier())
    body = (await client.get("/meetings/m1/minutes")).json()
    assert body["status"] == "generation_failed" and body["reason"] and body["draft"] is None
