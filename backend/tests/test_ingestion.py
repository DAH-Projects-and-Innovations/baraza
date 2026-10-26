from typing import Any

import pytest
from fastapi.testclient import TestClient

from baraza.api.segments import MAX_BATCH, get_segment_store
from baraza.core.ingestion import InMemorySegmentStore, SegmentStore, ingest_segments
from baraza.main import create_app


def raw(segment_id: str = "s1", **overrides: Any) -> dict[str, Any]:
    return {
        "segment_id": segment_id,
        "speaker": "Awa Example",
        "start": 0,
        "end": 3,
        "text": "Hello.",
    } | overrides


async def test_valid_segments_are_stored_in_order() -> None:
    store = InMemorySegmentStore()
    result = await ingest_segments(
        store, "m1", [raw("b", start=5, end=8), raw("a", start=0, end=4)]
    )
    assert result.accepted == 2
    assert result.rejected == []
    assert [s.segment_id for s in await store.list("m1")] == ["a", "b"]


async def test_invalid_segments_do_not_block_valid_ones() -> None:
    store = InMemorySegmentStore()
    result = await ingest_segments(
        store, "m1", [raw("a"), raw("b", start=9, end=1), raw("c", text=" ")]
    )
    assert result.accepted == 1
    assert [r.index for r in result.rejected] == [1, 2]
    assert len(await store.list("m1")) == 1


async def test_errors_never_echo_transcript_text() -> None:
    result = await ingest_segments(
        InMemorySegmentStore(), "m1", [raw(start=9, end=1, text="secret words")]
    )
    assert "secret words" not in result.model_dump_json()


async def test_resending_a_segment_replaces_it() -> None:
    store = InMemorySegmentStore()
    await ingest_segments(store, "m1", [raw("a", text="Hel", is_final=False)])
    await ingest_segments(store, "m1", [raw("a", text="Hello.")])
    stored = await store.list("m1")
    assert [(s.text, s.is_final) for s in stored] == [("Hello.", True)]


async def test_meeting_id_comes_from_the_caller() -> None:
    store = InMemorySegmentStore()
    await ingest_segments(store, "m1", [raw("a", meeting_id="other")])
    assert len(await store.list("m1")) == 1
    assert await store.list("other") == []


async def test_sql_store_upserts_and_orders() -> None:
    pytest.importorskip("aiosqlite")
    from sqlalchemy.ext.asyncio import create_async_engine

    from baraza.storage.sql import SqlSegmentStore

    engine = create_async_engine("sqlite+aiosqlite://")
    store = SqlSegmentStore(engine)
    await ingest_segments(
        store, "m1", [raw("b", start=5, end=8), raw("a", text="Hel", is_final=False)]
    )
    await ingest_segments(store, "m1", [raw("a", text="Hello.")])
    await ingest_segments(store, "m2", [raw("z")])
    stored = await store.list("m1")
    assert [(s.segment_id, s.text, s.is_final) for s in stored] == [
        ("a", "Hello.", True),
        ("b", "Hello.", True),
    ]
    await engine.dispose()


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    store = InMemorySegmentStore()
    app.dependency_overrides[get_segment_store] = lambda: store
    return TestClient(app)


def test_api_roundtrip(client: TestClient) -> None:
    response = client.post("/meetings/m1/segments", json=[raw("a"), raw("b", start=9, end=1)])
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert response.json()["rejected"][0]["index"] == 1
    listed = client.get("/meetings/m1/segments").json()
    assert [s["segment_id"] for s in listed] == ["a"]
    assert listed[0]["meeting_id"] == "m1"


def test_api_rejects_empty_and_oversized_batches(client: TestClient) -> None:
    assert client.post("/meetings/m1/segments", json=[]).status_code == 422
    too_many = [raw(str(i)) for i in range(MAX_BATCH + 1)]
    assert client.post("/meetings/m1/segments", json=too_many).status_code == 422


def test_store_protocol_is_satisfied() -> None:
    store: SegmentStore = InMemorySegmentStore()
    assert store is not None
