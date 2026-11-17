"""Regenerating a draft (issue #136) and recording the model (issue #89)."""

import asyncio

from fastapi.testclient import TestClient
from test_sprint3_flow import RecordingQueue, flow, start  # noqa: F401

from baraza.llm.client import FakeLLMClient
from baraza.storage.sql import SqlMeetingStore
from baraza.worker import generate_minutes_task

Flow = tuple[TestClient, SqlMeetingStore, RecordingQueue]

FIRST = '{"summary":"First draft"}'
SECOND = '{"summary":"Second draft"}'


class BrokenLLM:
    async def complete_json(self, *args, **kwargs) -> str:
        raise RuntimeError("model down")


def generate(store: SqlMeetingStore, capture_id: str, llm) -> None:
    asyncio.run(generate_minutes_task({"meeting_store": store, "llm": llm}, capture_id))


def draft(client: TestClient, store: SqlMeetingStore) -> str:
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    generate(store, capture_id, FakeLLMClient(FIRST))
    return capture_id


def test_the_draft_records_the_model_that_wrote_it(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = draft(client, store)
    meta = client.get(f"/meetings/{capture_id}/minutes/meta").json()
    assert meta["model_name"] and meta["prompt_version"]


def test_regenerating_keeps_the_previous_draft_as_a_revision(flow: Flow) -> None:  # noqa: F811
    client, store, queue = flow
    capture_id = draft(client, store)
    queued = len(queue.jobs)

    response = client.post(f"/meetings/{capture_id}/minutes/regenerate")
    assert response.status_code == 202
    assert len(queue.jobs) == queued + 1
    assert client.get(f"/captures/{capture_id}").json()["status"] == "processing"

    generate(store, capture_id, FakeLLMClient(SECOND))
    assert client.get(f"/meetings/{capture_id}/minutes").json()["summary"] == "Second draft"
    revisions = client.get(f"/meetings/{capture_id}/minutes/revisions").json()
    assert [r["version"] for r in revisions] == [1, 2]
    assert client.get(f"/meetings/{capture_id}/minutes/revisions/1").json()["summary"] == (
        "First draft"
    )


def test_manual_edits_are_kept_as_a_revision_when_regenerating(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = draft(client, store)
    minutes = client.get(f"/meetings/{capture_id}/minutes").json()
    minutes["summary"] = "Edited by a person"
    assert (
        client.put(
            f"/meetings/{capture_id}/minutes", json=minutes, headers={"If-Match": "1"}
        ).status_code
        == 200
    )
    client.post(f"/meetings/{capture_id}/minutes/regenerate")
    generate(store, capture_id, FakeLLMClient(SECOND))
    edited = client.get(f"/meetings/{capture_id}/minutes/revisions/2").json()
    assert edited["summary"] == "Edited by a person"


def test_validated_minutes_cannot_be_regenerated(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = draft(client, store)
    client.post(f"/meetings/{capture_id}/minutes/validate", headers={"If-Match": "1"})
    assert client.post(f"/meetings/{capture_id}/minutes/regenerate").status_code == 409


def test_there_must_be_a_draft_and_no_generation_running(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    assert client.post(f"/meetings/{capture_id}/minutes/regenerate").status_code == 404
    assert client.post("/meetings/unknown/minutes/regenerate").status_code == 404
    generate(store, capture_id, FakeLLMClient(FIRST))
    assert client.post(f"/meetings/{capture_id}/minutes/regenerate").status_code == 202
    assert client.post(f"/meetings/{capture_id}/minutes/regenerate").status_code == 409


def test_a_failed_regeneration_keeps_the_previous_draft(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = draft(client, store)
    client.post(f"/meetings/{capture_id}/minutes/regenerate")
    generate(store, capture_id, BrokenLLM())
    capture = client.get(f"/captures/{capture_id}").json()
    assert capture["status"] == "done" and "previous draft is kept" in capture["error"]
    assert client.get(f"/meetings/{capture_id}/minutes").json()["summary"] == "First draft"
