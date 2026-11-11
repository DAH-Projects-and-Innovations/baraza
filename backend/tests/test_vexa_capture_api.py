"""POST /captures with the real VexaAdapter against a mocked Vexa gateway."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.adapters.vexa import VexaAdapter
from baraza.api import dependencies
from baraza.api.dependencies import (
    GenerationQueue,
    get_capture_adapter,
    get_generation_queue,
    get_meeting_store,
)
from baraza.api.segments import get_segment_store
from baraza.config import Settings
from baraza.db.migrations import upgrade_database
from baraza.main import create_app
from baraza.storage.sql import SqlMeetingStore, SqlSegmentStore
from baraza.vexa.client import VexaClient

BASE = "http://vexa:8056"
MEET_URL = "https://meet.google.com/abc-defg-hij"
BOT = {
    "id": 42,
    "platform": "google_meet",
    "native_meeting_id": "abc-defg-hij",
    "status": "requested",
    "start_time": "2026-10-28T10:00:00Z",
}
SEGMENTS = [
    {"segment_id": "s1", "speaker": "Alice", "start": 0, "end": 3, "text": "We ship in March."},
    {"segment_id": "s2", "speaker": "Bob", "start": 3, "end": 6, "text": "I send the plan."},
]
REQUEST = {
    "meeting_url": MEET_URL,
    "title": "Fictional Vexa meeting",
    "template": "standard",
    "participants_informed": True,
}


class RecordingQueue(GenerationQueue):
    def __init__(self) -> None:
        self.jobs: list[str] = []

    async def enqueue(self, meeting_id: str) -> None:
        self.jobs.append(meeting_id)


class Holder:
    """Lets a test replace the adapter, like an API restart losing in-memory handles."""

    def __init__(self) -> None:
        self.settings = Settings(_env_file=None, vexa_api_key=SecretStr("fictional-key"))
        self.adapter = self.new_adapter()

    def new_adapter(self) -> VexaAdapter:
        return VexaAdapter(VexaClient(self.settings), self.settings)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[tuple[TestClient, Holder, RecordingQueue]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'vexa.db'}")
    asyncio.run(upgrade_database(engine))
    holder, queue = Holder(), RecordingQueue()
    app = create_app()
    app.dependency_overrides[get_meeting_store] = lambda: SqlMeetingStore(engine)
    app.dependency_overrides[get_segment_store] = lambda: SqlSegmentStore(engine)
    app.dependency_overrides[get_generation_queue] = lambda: queue
    app.dependency_overrides[get_capture_adapter] = lambda: holder.adapter
    with TestClient(app) as client:
        yield client, holder, queue
    asyncio.run(holder.adapter.client.aclose())
    asyncio.run(engine.dispose())


@respx.mock
def test_start_follow_restart_stop_and_ingest(
    api: tuple[TestClient, Holder, RecordingQueue],
) -> None:
    client, holder, queue = api
    respx.post(f"{BASE}/bots").respond(201, json=BOT)
    started = client.post("/captures", json=REQUEST)
    assert started.status_code == 201, started.text
    capture_id = started.json()["capture_id"]
    assert capture_id == "42"
    assert started.json()["simulated"] is False
    assert started.json()["status"] == "waiting_admission"

    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "active"})
    assert client.get("/captures/42").json()["status"] == "capturing"

    # The API restarts: the new adapter knows nothing, the meeting record is enough.
    asyncio.run(holder.adapter.client.aclose())
    holder.adapter = holder.new_adapter()
    respx.delete(f"{BASE}/bots/google_meet/abc-defg-hij").respond(
        200, json={"status": "stopping", "meeting_id": 42}
    )
    stopped = client.post("/captures/42/stop")
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["stop_requested"] is True
    assert stopped.json()["status"] == "capturing"  # the final transcript is not flushed yet
    assert queue.jobs == []

    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "completed"})
    respx.get(f"{BASE}/transcripts/by-id/42").respond(
        200, json={**BOT, "status": "completed", "segments": SEGMENTS}
    )
    done = client.get("/captures/42")
    assert done.json()["status"] == "processing"
    assert queue.jobs == ["42"]
    assert len(client.get("/meetings/42/segments").json()) == 2


@respx.mock
def test_vexa_refusal_returns_502_without_details(
    api: tuple[TestClient, Holder, RecordingQueue],
) -> None:
    client, _, _ = api
    respx.post(f"{BASE}/bots").respond(500, json={"detail": "private upstream detail"})
    response = client.post("/captures", json=REQUEST)
    assert response.status_code == 502
    assert "private" not in response.text


def test_adapter_selection_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    def settings(**values: object) -> Settings:
        return Settings(_env_file=None, **values)  # type: ignore[arg-type]

    cases = [
        (settings(), type(None)),
        (settings(capture_mode="vexa"), type(None)),  # no key: explicit 503, never a guess
        (settings(capture_mode="vexa", vexa_api_key=SecretStr("k")), VexaAdapter),
    ]
    for config, expected in cases:
        dependencies.get_capture_adapter.cache_clear()
        monkeypatch.setattr(dependencies, "get_settings", lambda config=config: config)
        adapter = dependencies.get_capture_adapter()
        assert isinstance(adapter, expected)
        if isinstance(adapter, VexaAdapter):
            asyncio.run(dependencies.close_capture_adapter())
    dependencies.get_capture_adapter.cache_clear()


def test_restore_rejects_a_non_meet_url() -> None:
    holder = Holder()
    with pytest.raises(ValueError, match="Google Meet"):
        holder.adapter.restore_capture("42", "https://evil.example/abc-defg-hij")
    holder.adapter.restore_capture("42", MEET_URL)
    assert holder.adapter.handle("42").native_meeting_id == "abc-defg-hij"
    asyncio.run(holder.adapter.client.aclose())
