import httpx
import pytest
import respx
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.adapters.vexa import VexaAdapter
from baraza.api.vexa_capture import get_capture_service, get_capture_store
from baraza.config import Settings
from baraza.core.captures import VexaCaptureService
from baraza.db.migrations import upgrade_database
from baraza.main import create_app
from baraza.storage.captures import SqlCaptureStore
from baraza.storage.sql import SqlSegmentStore
from baraza.vexa.client import VexaClient

URL = "https://meet.google.com/abc-defg-hij"
BASE = "http://vexa:8056"
BOT = {
    "id": 42,
    "platform": "google_meet",
    "native_meeting_id": "abc-defg-hij",
    "status": "requested",
}


@pytest.fixture
async def capture_api(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    await upgrade_database(engine)
    settings = Settings(_env_file=None, vexa_api_key=SecretStr("fictional-key"), vexa_retries=0)
    vexa = VexaClient(settings)
    store = SqlCaptureStore(engine)
    service = VexaCaptureService(VexaAdapter(vexa, settings), store, SqlSegmentStore(engine))
    app = create_app()
    app.dependency_overrides[get_capture_service] = lambda: service
    app.dependency_overrides[get_capture_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as api:
            yield api, service
    finally:
        await vexa.aclose()
        await engine.dispose()


@respx.mock
async def test_capture_http_lifecycle(capture_api):
    api, service = capture_api
    spawn = respx.post(f"{BASE}/bots").respond(201, json=BOT)
    assert (await api.get("/meetings/m1/status")).status_code == 404
    response = await api.post("/meetings/m1/capture", json={"meeting_url": URL})
    assert response.status_code == 201
    assert response.json() == {"capture_id": "42"}
    assert (await api.get("/meetings/m1/status")).json()["status"] == "pending"
    assert (await api.post("/meetings/m1/capture", json={"meeting_url": URL})).status_code == 409
    assert spawn.call_count == 1
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "active"})
    transcript = respx.get(f"{BASE}/transcripts/by-id/42").respond(
        200, json={**BOT, "status": "active", "segments": []}
    )
    capture = (await service.captures.captures())[0]
    await service.poll(capture)
    assert (await api.get("/meetings/m1/status")).json()["status"] == "capturing"
    respx.delete(f"{BASE}/bots/google_meet/abc-defg-hij").respond(
        200, json={"status": "stopping", "meeting_id": 42}
    )
    assert (await api.post("/meetings/m1/capture/stop")).status_code == 202
    assert (await api.get("/meetings/m1/status")).json()["status"] == "capturing"
    transcript.respond(200, json={**BOT, "status": "completed", "segments": []})
    await service.poll(capture)
    status = (await api.get("/meetings/m1/status")).json()
    assert status["status"] == "processing"
    assert len(status["transitions"]) == 3
    assert all(t["at"] for t in status["transitions"])
    assert (await api.post("/meetings/m1/capture/stop")).status_code == 409


@respx.mock
async def test_failed_spawn_exposes_error_without_upstream_details(capture_api):
    api, _ = capture_api
    respx.post(f"{BASE}/bots").respond(403, text="private upstream details")
    response = await api.post("/meetings/m1/capture", json={"meeting_url": URL})
    assert response.status_code == 502
    assert "private" not in response.text
    assert (await api.get("/meetings/m1/status")).json()["status"] == "error"


async def test_invalid_url_does_not_create_meeting(capture_api):
    api, _ = capture_api
    response = await api.post("/meetings/m1/capture", json={"meeting_url": "https://example.org"})
    assert response.status_code == 422
    assert (await api.get("/meetings/m1/status")).status_code == 404


async def test_disabled_capture_returns_service_unavailable(monkeypatch):
    from baraza.api import vexa_capture

    monkeypatch.setattr(vexa_capture, "get_settings", lambda: Settings(_env_file=None))
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api,
    ):
        assert (
            await api.post("/meetings/m1/capture", json={"meeting_url": URL})
        ).status_code == 503


@respx.mock
async def test_active_bot_with_delayed_transcript_still_shows_capturing(capture_api):
    api, service = capture_api
    respx.post(f"{BASE}/bots").respond(201, json=BOT)
    await api.post("/meetings/m1/capture", json={"meeting_url": URL})
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "active"})
    tx = respx.get(f"{BASE}/transcripts/by-id/42").respond(404)
    capture = (await service.captures.captures())[0]
    with pytest.raises(httpx.HTTPStatusError):
        await service.poll(capture)
    assert (await api.get("/meetings/m1/status")).json()["status"] == "capturing"
    assert len(await service.captures.captures()) == 1
    tx.respond(200, json={**BOT, "status": "completed", "segments": []})
    await service.poll(capture)
    assert (await api.get("/meetings/m1/status")).json()["status"] == "processing"
