"""Exercise the frontend/backend contract with durable storage and no external services."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.adapters.base import CaptureStatus
from baraza.adapters.fake import FakeCaptureAdapter
from baraza.api.dependencies import (
    GenerationQueue,
    get_capture_adapter,
    get_generation_queue,
    get_meeting_store,
)
from baraza.api.segments import get_segment_store
from baraza.core.transcript import Transcript
from baraza.db.migrations import upgrade_database
from baraza.llm.client import FakeLLMClient
from baraza.main import create_app
from baraza.storage.sql import SqlMeetingStore, SqlSegmentStore
from baraza.worker import generate_minutes_task

REQUEST = {
    "meeting_url": "https://meet.google.com/abc-defg-hij",
    "title": "Fictional sprint review",
    "template": "standard",
    "participants_informed": True,
}


class RecordingQueue(GenerationQueue):
    def __init__(self) -> None:
        self.jobs: list[str] = []
        self.fail = False

    async def enqueue(self, meeting_id: str) -> None:
        if self.fail:
            raise ConnectionError("private connection details")
        self.jobs.append(meeting_id)


@pytest.fixture
def flow(tmp_path: Path) -> Iterator[tuple[TestClient, SqlMeetingStore, RecordingQueue]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}")
    asyncio.run(upgrade_database(engine))
    store = SqlMeetingStore(engine)
    queue = RecordingQueue()
    adapter = FakeCaptureAdapter()
    app = create_app()
    app.dependency_overrides[get_meeting_store] = lambda: store
    app.dependency_overrides[get_segment_store] = lambda: SqlSegmentStore(engine)
    app.dependency_overrides[get_generation_queue] = lambda: queue
    app.dependency_overrides[get_capture_adapter] = lambda: adapter
    with TestClient(app) as client:
        yield client, store, queue
    asyncio.run(engine.dispose())


def start(client: TestClient) -> str:
    response = client.post("/captures", json=REQUEST)
    assert response.status_code == 201, response.text
    assert response.json()["simulated"] is True
    return str(response.json()["capture_id"])


def test_start_stop_ingest_generate_read_and_reopen(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, store, queue = flow
    capture_id = start(client)
    assert client.get(f"/captures/{capture_id}").json()["status"] == "capturing"
    assert client.get(f"/meetings/{capture_id}/minutes").status_code == 404
    # A partial live segment must be replaced by the canonical final transcript.
    client.post(
        f"/meetings/{capture_id}/segments",
        json=[
            {
                "segment_id": "live-1",
                "speaker_id": "2",
                "start_time": 0,
                "end_time": 2,
                "text": "A partial phrase",
                "is_final": False,
            }
        ],
    )
    stopped = client.post(f"/captures/{capture_id}/stop")
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "processing"
    assert client.post(f"/captures/{capture_id}/stop").status_code == 200
    assert queue.jobs == [capture_id]
    segments = client.get(f"/meetings/{capture_id}/segments").json()
    assert len(segments) == 3
    assert all(s["is_final"] for s in segments)
    llm = FakeLLMClient(
        '{"summary":"Fictional draft","actions":[{"text":"Review the budget",'
        '"owner":null,"due_date":null,"source":{"segment_indices":[2]}}]}'
    )
    asyncio.run(generate_minutes_task({"meeting_store": store, "llm": llm}, capture_id))
    assert client.get(f"/captures/{capture_id}").json()["status"] == "done"
    minutes = client.get(f"/meetings/{capture_id}/minutes").json()
    assert minutes["actions"][0]["owner"] is None
    assert minutes["actions"][0]["due_date"] is None
    # A new store instance reads the same persisted meeting and draft.
    reopened = SqlMeetingStore(store._engine)
    saved = asyncio.run(reopened.get(capture_id))
    assert saved is not None and saved.minutes is not None
    assert saved.minutes.summary == "Fictional draft"
    assert len(llm.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"meeting_url": "https://meet.google.com.attacker.example/abc-defg-hij"},
        {"meeting_url": "https://meet.google.com/abc-defg-hij#secret"},
        {"participants_informed": False},
        {"participants_informed": None},
        {"title": " "},
        {"template": "unsupported"},
    ],
)
def test_invalid_start_never_queues(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
    change: dict[str, Any],
) -> None:
    client, _, queue = flow
    assert client.post("/captures", json=REQUEST | change).status_code == 422
    assert queue.jobs == []


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "9.0"},
        {"segments": []},
        {"segments": [{"speaker": "Example", "text": "private transcript", "start": 8, "end": 2}]},
        {"segments": [{"speaker": "Example", "text": " ", "start": 0, "end": 1}]},
    ],
)
def test_bad_transcript_marks_failure_without_echoing_text(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
    transcript: Transcript,
    change: dict[str, Any],
) -> None:
    client, _, queue = flow
    capture_id = start(client)
    response = client.post(
        f"/meetings/{capture_id}/transcript", json=transcript.model_dump(mode="json") | change
    )
    assert response.status_code == 422
    assert "private transcript" not in response.text
    assert client.get(f"/captures/{capture_id}").json()["status"] == "failed"
    assert queue.jobs == []


def test_valid_final_transcript_triggers_one_generation(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
    transcript: Transcript,
) -> None:
    client, _, queue = flow
    capture_id = start(client)
    payload = transcript.model_dump(mode="json")
    assert client.post(f"/meetings/{capture_id}/transcript", json=payload).status_code == 202
    assert client.post(f"/meetings/{capture_id}/transcript", json=payload).status_code == 409
    assert queue.jobs == [capture_id]
    stored = client.get(f"/meetings/{capture_id}/transcript").json()
    assert stored["participants"] == payload["participants"]


def test_generation_failure_can_be_retried(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, store, queue = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    asyncio.run(
        generate_minutes_task({"meeting_store": store, "llm": FakeLLMClient("invalid")}, capture_id)
    )
    status = client.get(f"/captures/{capture_id}").json()
    assert status["status"] == "failed" and status["can_retry"]
    assert "invalid" not in status["error"]
    assert client.post(f"/meetings/{capture_id}/retry").status_code == 202
    assert len(queue.jobs) == 2
    asyncio.run(
        generate_minutes_task(
            {"meeting_store": store, "llm": FakeLLMClient('{"summary":"Recovered"}')}, capture_id
        )
    )
    assert client.get(f"/meetings/{capture_id}/minutes").json()["summary"] == "Recovered"


def test_queue_outage_keeps_transcript_for_retry(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, _, queue = flow
    capture_id = start(client)
    queue.fail = True
    response = client.post(f"/captures/{capture_id}/stop")
    assert response.status_code == 503
    assert "private connection" not in response.text
    assert client.get(f"/meetings/{capture_id}/transcript").status_code == 200
    queue.fail = False
    assert client.post(f"/meetings/{capture_id}/retry").status_code == 202


def test_unknown_meeting_and_unconfigured_capture_are_explicit(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, _, _ = flow
    assert client.get("/captures/unknown").status_code == 404
    assert client.post("/captures/unknown/stop").status_code == 404
    assert client.get("/meetings/unknown/minutes").status_code == 404
    client.app.dependency_overrides[get_capture_adapter] = lambda: None
    assert client.post("/captures", json=REQUEST).status_code == 503


def test_browser_origin_is_allowed(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, _, _ = flow
    response = client.options(
        "/captures",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_late_segments_cannot_change_the_final_transcript(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, _, _ = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    before = client.get(f"/meetings/{capture_id}/segments").json()
    response = client.post(
        f"/meetings/{capture_id}/segments",
        json=[
            {
                "segment_id": "late",
                "speaker": "Example",
                "start": 100,
                "end": 110,
                "text": "Late partial",
                "is_final": False,
            }
        ],
    )
    assert response.status_code == 409
    assert client.get(f"/meetings/{capture_id}/segments").json() == before


def test_stop_waits_for_provider_completion(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    class AsyncStopAdapter(FakeCaptureAdapter):
        name = "external-test-provider"

        def __init__(self) -> None:
            self.stopped = False

        async def stop(self, capture_id: str) -> None:
            self.stopped = True

        async def status(self, capture_id: str) -> CaptureStatus:
            return CaptureStatus.PROCESSING if self.stopped else CaptureStatus.CAPTURING

    client, _, queue = flow
    adapter = AsyncStopAdapter()
    client.app.dependency_overrides[get_capture_adapter] = lambda: adapter
    capture_id = client.post("/captures", json=REQUEST).json()["capture_id"]
    response = client.post(f"/captures/{capture_id}/stop")
    assert response.json()["stop_requested"] is True
    assert queue.jobs == []
    assert client.post(f"/captures/{capture_id}/stop").status_code == 200
    assert client.get(f"/captures/{capture_id}").json()["status"] == "processing"
    assert queue.jobs == [capture_id]


def test_alternate_meet_url_is_canonicalized(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, store, _ = flow
    response = client.post(
        "/captures",
        json=REQUEST
        | {
            "meeting_url": "https://meet.google.com/meet/abc-defg-hij?authuser=0",
        },
    )
    assert response.status_code == 201
    meeting = asyncio.run(store.get(response.json()["capture_id"]))
    assert meeting is not None
    assert meeting.meeting_url == "https://meet.google.com/abc-defg-hij?authuser=0"


def test_out_of_range_model_sources_fail_safely(
    flow: tuple[TestClient, SqlMeetingStore, RecordingQueue],
) -> None:
    client, store, _ = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    llm = FakeLLMClient(
        '{"summary":"Invalid sources","decisions":[{"text":"Example",'
        '"source":{"segment_indices":[99]}}]}'
    )
    asyncio.run(generate_minutes_task({"meeting_store": store, "llm": llm}, capture_id))
    assert client.get(f"/captures/{capture_id}").json()["status"] == "failed"
    assert client.get(f"/meetings/{capture_id}/minutes").status_code == 404
