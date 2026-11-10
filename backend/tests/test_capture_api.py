import httpx
import pytest
import respx
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.adapters.vexa import VexaAdapter
from baraza.api.captures import get_capture_service, get_capture_store
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
    from baraza.api import captures

    monkeypatch.setattr(captures, "get_settings", lambda: Settings(_env_file=None))
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api,
    ):
        assert (
            await api.post("/meetings/m1/capture", json={"meeting_url": URL})
        ).status_code == 503


@respx.mock
async def test_frontend_contract_keeps_one_local_id(capture_api):
    api, service = capture_api
    respx.post(f"{BASE}/bots").respond(201, json=BOT)
    response = await api.post("/captures", json={"meeting_url": URL})
    assert response.status_code == 201
    meeting_id = response.json()["capture_id"]
    assert meeting_id != str(BOT["id"])
    status = (await api.get(f"/captures/{meeting_id}")).json()
    assert status["capture_id"] == meeting_id
    assert status["status"] == "waiting_admission"
    assert status["meeting_status"] == "pending"
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "completed"})
    respx.get(f"{BASE}/transcripts/by-id/42").respond(
        200,
        json={
            **BOT,
            "status": "completed",
            "segments": [{"segment_id": "s1", "start": 0, "end": 1, "text": "Test"}],
        },
    )
    await service.poll((await service.captures.captures())[0])
    status = (await api.get(f"/captures/{meeting_id}")).json()
    assert status["status"] == "processing"
    assert status["meeting_status"] == "processing"
    assert (await service.segments.list(meeting_id))[0].meeting_id == meeting_id
    assert (await api.post(f"/captures/{meeting_id}/stop")).status_code == 409


@pytest.mark.parametrize(
    ("business_states", "expected"),
    [
        (["capturing"], "capturing"),
        (["processing"], "processing"),
        (["processing", "draft_ready"], "done"),
        (["processing", "draft_ready", "validated"], "done"),
        (["error"], "failed"),
    ],
)
async def test_frontend_status_preserves_business_state(capture_api, business_states, expected):
    from baraza.core.meetings import MeetingStatus

    api, service = capture_api
    await service.captures.create("m1")
    for status in business_states:
        await service.captures.transition("m1", MeetingStatus(status))
    response = await api.get("/captures/m1")
    assert response.json()["status"] == expected
    assert response.json()["meeting_status"] == business_states[-1]
    assert len(response.json()["transitions"]) == len(business_states) + 1


async def test_unknown_frontend_capture_returns_not_found(capture_api):
    api, _ = capture_api
    assert (await api.get("/captures/missing")).status_code == 404


async def test_browser_preflight_allows_only_configured_origin(capture_api):
    api, _ = capture_api
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = await api.options("/captures", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    headers["Origin"] = "https://untrusted.example"
    response = await api.options("/captures", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


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
    assert (await api.get("/captures/m1")).json()["status"] == "capturing"
    assert len(await service.captures.captures()) == 1
    tx.respond(200, json={**BOT, "status": "completed", "segments": []})
    await service.poll(capture)
    assert (await api.get("/captures/m1")).json()["status"] == "processing"
