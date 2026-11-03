import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from adapters.contract import CaptureAdapterContract
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.adapters.vexa import STATUS_MAP, VexaAdapter, map_segments
from baraza.config import Settings
from baraza.core.captures import VexaCaptureService
from baraza.main import create_app
from baraza.storage.captures import SqlCaptureStore
from baraza.storage.sql import SqlSegmentStore
from baraza.vexa.client import BotResponse, TranscriptResponse, VexaClient

BASE = "http://vexa:8056"
URL = "https://meet.google.com/abc-defg-hij"
BOT = {
    "id": 42,
    "platform": "google_meet",
    "native_meeting_id": "abc-defg-hij",
    "status": "requested",
    "start_time": "2026-10-28T10:00:00Z",
}
SEGMENTS = [
    {
        "segment_id": "s1",
        "speaker": "Alice",
        "start": 0,
        "end": 1,
        "text": "Bonjour",
        "language": "fr",
        "completed": True,
    },
    {
        "segment_id": "s2",
        "speaker": None,
        "speaker_id": "opaque-id",
        "start": 1,
        "end": 2,
        "text": "Oui",
        "completed": True,
    },
]


def payload(state="completed", segments=None):
    return {**BOT, "status": state, "segments": SEGMENTS if segments is None else segments}


@pytest.fixture
async def client():
    settings = Settings(_env_file=None, vexa_api_key=SecretStr("test-secret"))
    client = VexaClient(settings)
    yield client
    await client.aclose()


@pytest.fixture
def meeting_url():
    return URL


@pytest.fixture
async def adapter(client):
    with respx.mock as mock:
        mock.post(f"{BASE}/bots").respond(201, json=BOT)
        mock.get(f"{BASE}/meetings/42").mock(
            side_effect=[
                httpx.Response(200, json={**BOT, "status": s})
                for s in ["awaiting_admission", "active", "completed"]
            ]
        )
        mock.delete(f"{BASE}/bots/google_meet/abc-defg-hij").respond(
            200,
            json={"status": "stopping", "meeting_id": 42},
        )
        mock.get(f"{BASE}/transcripts/by-id/42").respond(200, json=payload())
        yield VexaAdapter(client, Settings(_env_file=None))


class TestVexaContract(CaptureAdapterContract):
    pass


@respx.mock
async def test_bot_payload_and_auth(client):
    route = respx.post(f"{BASE}/bots").respond(201, json=BOT)
    settings = Settings(_env_file=None, vexa_bot_name="Baraza test")
    adapter = VexaAdapter(client, settings)
    assert await adapter.start(URL) == "42"
    request = route.calls.last.request
    assert request.headers["X-API-Key"] == "test-secret"
    assert json.loads(request.content) == {
        "platform": "google_meet",
        "native_meeting_id": "abc-defg-hij",
        "meeting_url": URL,
        "bot_name": "Baraza test",
        "recording_enabled": False,
        "transcribe_enabled": True,
    }


@pytest.mark.parametrize("state", list(STATUS_MAP))
@respx.mock
async def test_status_mapping(client, state):
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": state})
    adapter = VexaAdapter(client, Settings(_env_file=None))
    adapter.restore(BotResponse.model_validate(BOT))
    assert await adapter.status("42") == STATUS_MAP[state]


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
@respx.mock
async def test_transient_retries(client, code):
    route = respx.get(f"{BASE}/meetings/42").mock(
        side_effect=[
            httpx.Response(code),
            httpx.Response(200, json=BOT),
        ]
    )
    with patch("baraza.vexa.client.asyncio.sleep", new_callable=AsyncMock):
        assert (await client.get_bot("42")).id == 42
    assert route.call_count == 2


@pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422])
@respx.mock
async def test_permanent_errors_not_retried(client, code):
    route = respx.get(f"{BASE}/meetings/42").respond(code)
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_bot("42")
    assert route.call_count == 1


@respx.mock
async def test_timeout_retries_are_bounded(client):
    route = respx.get(f"{BASE}/meetings/42").mock(side_effect=httpx.ReadTimeout("timeout"))
    with (
        patch("baraza.vexa.client.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(httpx.ReadTimeout),
    ):
        await client.get_bot("42")
    assert route.call_count == 3


@respx.mock
async def test_spawn_is_not_retried_after_timeout(client):
    route = respx.post(f"{BASE}/bots").mock(side_effect=httpx.ReadTimeout("timeout"))
    with pytest.raises(httpx.ReadTimeout):
        await VexaAdapter(client, Settings(_env_file=None)).start(URL)
    assert route.call_count == 1


@pytest.mark.parametrize("method", ["status", "stop", "fetch_transcript"])
@respx.mock
async def test_unknown_ids_rejected_before_http(client, method):
    adapter = VexaAdapter(client, Settings(_env_file=None))
    with pytest.raises(ValueError, match="Unknown Vexa capture"):
        await getattr(adapter, method)("unknown")


@respx.mock
async def test_wrong_meeting_is_rejected(client):
    adapter = VexaAdapter(client, Settings(_env_file=None))
    adapter.restore(BotResponse.model_validate(BOT))
    respx.get(f"{BASE}/transcripts/by-id/42").respond(200, json={**payload(), "id": 99})
    with pytest.raises(ValueError, match="does not match"):
        await adapter.fetch_transcript("42")


def test_segment_mapping_and_final_filter():
    raw = payload(
        segments=[
            *SEGMENTS,
            {**SEGMENTS[1], "segment_id": "s3", "start": 2, "end": 3},
            {**SEGMENTS[1], "segment_id": "s4", "speaker_id": "second", "start": 3, "end": 4},
            {**SEGMENTS[1], "segment_id": "s5", "speaker_id": None, "start": 4, "end": 5},
        ]
    )
    mapped = map_segments(TranscriptResponse.model_validate(raw), "local-meeting")
    assert [s.speaker for s in mapped] == [
        "Alice",
        "Speaker 1",
        "Speaker 1",
        "Speaker 2",
        "Speaker 3",
    ]
    assert {s.meeting_id for s in mapped} == {"local-meeting"}
    assert mapped[0].language == "fr"


@pytest.mark.parametrize("updates", [{"end": -1}, {"start": 10}, {"start": float("inf")}])
def test_invalid_segment_is_rejected(updates):
    with pytest.raises(ValidationError):
        TranscriptResponse.model_validate(payload(segments=[{**SEGMENTS[0], **updates}]))


@respx.mock
async def test_full_meeting_ingestion_and_restart(client, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'capture.db'}")
    store = SqlCaptureStore(engine)
    segments = SqlSegmentStore(engine)
    service = VexaCaptureService(VexaAdapter(client, Settings(_env_file=None)), store, segments)
    respx.post(f"{BASE}/bots").respond(201, json=BOT)
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "awaiting_admission"})
    assert await service.start("m1", URL) == "42"
    capture = (await store.captures())[0]
    await service.poll(capture)
    assert (await store.get("m1")).status == "pending"
    assert await segments.list("m1") == []

    # Rebuild the service with an empty adapter registry, as after restarting the worker.
    service = VexaCaptureService(
        VexaAdapter(client, Settings(_env_file=None)),
        SqlCaptureStore(engine),
        segments,
    )
    route = respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "active"})
    tx = respx.get(f"{BASE}/transcripts/by-id/42").respond(200, json=payload("active"))
    await service.poll(capture)
    assert (await store.get("m1")).status == "capturing"
    route.respond(200, json={**BOT, "status": "completed"})
    tx.respond(200, json=payload())
    await service.poll(capture)
    assert (await store.get("m1")).status == "processing"
    assert await store.captures() == []
    assert len(await segments.list("m1")) == 2
    history = (await store.get("m1")).transitions
    await service.poll(capture)  # replay after an ambiguous DB acknowledgement
    assert len(await segments.list("m1")) == 2
    assert (await store.get("m1")).transitions == history
    await engine.dispose()


async def test_no_webhook_ingress_even_on_replay():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        for _ in range(2):
            response = await c.post("/webhooks/vexa", json={"bot_id": 42, "status": "completed"})
            assert response.status_code == 404


def test_api_key_is_required_and_hidden():
    settings = Settings(_env_file=None, vexa_api_key=SecretStr(""))
    with pytest.raises(ValueError, match="API_KEY"):
        VexaClient(settings)
    settings = Settings(_env_file=None, vexa_api_key=SecretStr("do-not-print"))
    assert "do-not-print" not in repr(settings)
    assert "do-not-print" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "url",
    [
        "http://meet.google.com/abc-defg-hij",
        "https://meet.google.com.evil.test/abc-defg-hij",
        "https://user@meet.google.com/abc-defg-hij",
        "https://meet.google.com/not-a-meeting",
        "https://127.0.0.1/abc-defg-hij",
    ],
)
@respx.mock
async def test_invalid_meeting_urls_never_spawn(client, url):
    with pytest.raises(ValueError, match="Google Meet"):
        await VexaAdapter(client, Settings(_env_file=None)).start(url)


@respx.mock
async def test_unknown_bot_state_is_not_assumed_completed(client):
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "new_state"})
    adapter = VexaAdapter(client, Settings(_env_file=None))
    adapter.restore(BotResponse.model_validate(BOT))
    with pytest.raises(ValidationError):
        await adapter.status("42")


@respx.mock
async def test_final_transcript_excludes_partial_segments(client):
    adapter = VexaAdapter(client, Settings(_env_file=None))
    adapter.restore(BotResponse.model_validate(BOT))
    respx.get(f"{BASE}/transcripts/by-id/42").respond(
        200,
        json=payload(
            segments=[
                *SEGMENTS,
                {**SEGMENTS[0], "segment_id": "partial", "completed": False},
            ]
        ),
    )
    transcript = await adapter.fetch_transcript("42")
    assert len(transcript.segments) == 2
    assert transcript.language == "fr"
    assert transcript.meeting.platform == "google_meet"


@pytest.mark.parametrize("state", ["completed", "failed"])
@respx.mock
async def test_terminal_state_without_observed_active(client, tmp_path, state):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'fast.db'}")
    captures = SqlCaptureStore(engine)
    segments = SqlSegmentStore(engine)
    service = VexaCaptureService(VexaAdapter(client, Settings(_env_file=None)), captures, segments)
    respx.post(f"{BASE}/bots").respond(201, json=BOT)
    await service.start("fast", URL)
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": state})
    if state == "completed":
        respx.get(f"{BASE}/transcripts/by-id/42").respond(200, json=payload())
    await service.poll((await captures.captures())[0])
    assert (await captures.get("fast")).status == (
        "processing" if state == "completed" else "error"
    )
    assert await captures.captures() == []
    assert len(await segments.list("fast")) == (2 if state == "completed" else 0)
    await engine.dispose()


@respx.mock
async def test_bad_transcript_does_not_finish_or_ingest(client, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bad.db'}")
    captures = SqlCaptureStore(engine)
    segments = SqlSegmentStore(engine)
    service = VexaCaptureService(VexaAdapter(client, Settings(_env_file=None)), captures, segments)
    respx.post(f"{BASE}/bots").respond(201, json=BOT)
    await service.start("bad", URL)
    capture = (await captures.captures())[0]
    respx.get(f"{BASE}/meetings/42").respond(200, json={**BOT, "status": "completed"})
    tx = respx.get(f"{BASE}/transcripts/by-id/42").respond(
        200,
        json={**payload(), "native_meeting_id": "different"},
    )
    with pytest.raises(ValueError, match="does not match"):
        await service.poll(capture)
    assert await segments.list("bad") == []
    tx.respond(200, json=payload(segments=[{**SEGMENTS[0], "end": -1}]))
    with pytest.raises(ValidationError):
        await service.poll(capture)
    assert (await captures.get("bad")).status == "pending"
    assert len(await captures.captures()) == 1
    assert await segments.list("bad") == []
    await engine.dispose()
