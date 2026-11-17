"""Meeting history and human review of the minutes (issue #135)."""

import asyncio
from typing import Any

from fastapi.testclient import TestClient
from test_sprint3_flow import REQUEST, RecordingQueue, flow, start  # noqa: F401

from baraza.llm.client import FakeLLMClient
from baraza.storage.sql import SqlMeetingStore
from baraza.worker import generate_minutes_task

Flow = tuple[TestClient, SqlMeetingStore, RecordingQueue]

DRAFT = (
    '{"summary":"Fictional draft","actions":[{"text":"Review the budget",'
    '"owner":null,"due_date":null,"source":{"segment_indices":[2]}}]}'
)


def meeting_with_draft(client: TestClient, store: SqlMeetingStore) -> str:
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    llm = FakeLLMClient(DRAFT)
    asyncio.run(generate_minutes_task({"meeting_store": store, "llm": llm}, capture_id))
    return capture_id


def edited(summary: str = "Reviewed summary", owner: str | None = "Awa Example") -> dict[str, Any]:
    return {
        "summary": summary,
        "actions": [
            {
                "text": "Review the budget",
                "owner": owner,
                "due_date": "2026-11-20",
                "source": {"segment_indices": [2]},
            }
        ],
    }


def test_browser_may_save_minutes_with_if_match(flow: Flow) -> None:  # noqa: F811
    """The preflight of a cross-origin PUT with If-Match must be accepted (frontend on :3000)."""
    client, _, _ = flow
    allowed = client.options(
        "/meetings/any/minutes",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,if-match",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    refused = client.options(
        "/meetings/any/minutes",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,if-match",
        },
    )
    assert "access-control-allow-origin" not in refused.headers


def test_history_is_empty_then_lists_meetings_most_recent_first(flow: Flow) -> None:  # noqa: F811
    client, _, _ = flow
    assert client.get("/meetings").json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
    first = start(client)
    second = start(client)
    items = client.get("/meetings").json()["items"]
    assert [i["meeting_id"] for i in items] == [second, first]
    assert items[0]["title"] == REQUEST["title"]
    assert items[0]["minutes_status"] is None
    assert items[0]["needs_review"] is False
    assert client.get("/meetings?limit=1&offset=1").json()["items"][0]["meeting_id"] == first
    assert client.get("/meetings?limit=0").status_code == 422


def test_draft_is_listed_as_needing_review_with_counts(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    other = start(client)
    review = client.get("/meetings?needs_review=true").json()
    assert [i["meeting_id"] for i in review["items"]] == [capture_id]
    item = review["items"][0]
    assert item["status"] == "done" and item["minutes_status"] == "draft"
    assert item["counts"]["actions"] == 1
    assert item["counts"]["actions_without_owner"] == 1
    assert item["counts"]["actions_without_deadline"] == 1
    assert item["participants"] >= 1 and item["duration_seconds"] > 0
    assert (
        client.get("/meetings?status=waiting_admission").json()["items"][0]["meeting_id"] == other
    )


def test_minutes_carry_a_version_and_the_assistant_draft_is_kept(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    response = client.get(f"/meetings/{capture_id}/minutes")
    assert response.headers["etag"] == '"1"'
    assert response.headers["x-minutes-status"] == "draft"
    meta = client.get(f"/meetings/{capture_id}/minutes/meta").json()
    assert (meta["status"], meta["version"], meta["validated_by"]) == ("draft", 1, None)
    revisions = client.get(f"/meetings/{capture_id}/minutes/revisions").json()
    assert [(r["version"], r["saved_by"]) for r in revisions] == [(1, "assistant")]


def test_no_minutes_yet_is_a_clear_404(flow: Flow) -> None:  # noqa: F811
    client, _, _ = flow
    capture_id = start(client)
    assert client.get(f"/meetings/{capture_id}/minutes/meta").status_code == 404
    put = client.put(f"/meetings/{capture_id}/minutes", json=edited(), headers={"If-Match": "1"})
    assert put.status_code == 404
    post = client.post(f"/meetings/{capture_id}/minutes/validate", headers={"If-Match": "1"})
    assert post.status_code == 404
    assert client.get("/meetings/unknown/minutes/meta").status_code == 404


def test_saving_needs_the_version_and_rejects_a_stale_one(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    url = f"/meetings/{capture_id}/minutes"
    assert client.put(url, json=edited()).status_code == 428
    assert client.put(url, json=edited(), headers={"If-Match": "abc"}).status_code == 400
    stale = client.put(url, json=edited(), headers={"If-Match": '"7"'})
    assert stale.status_code == 412
    assert stale.headers["etag"] == '"1"'

    saved = client.put(url, json=edited(), headers={"If-Match": '"1"'})
    assert saved.status_code == 200, saved.text
    assert saved.headers["etag"] == '"2"'
    assert saved.json()["version"] == 2 and saved.json()["status"] == "draft"
    assert client.get(url).json()["summary"] == "Reviewed summary"
    assert client.get(url).json()["actions"][0]["owner"] == "Awa Example"

    # Two people editing the same version: the second one is told to reload.
    assert client.put(url, json=edited("Other"), headers={"If-Match": '"1"'}).status_code == 412


def test_every_save_is_in_the_history_and_the_original_stays_readable(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    url = f"/meetings/{capture_id}/minutes"
    client.put(url, json=edited(), headers={"If-Match": "1"})
    revisions = client.get(f"{url}/revisions").json()
    assert [(r["version"], r["saved_by"]) for r in revisions] == [
        (1, "assistant"),
        (2, "local-user"),
    ]
    assert client.get(f"{url}/revisions/1").json()["summary"] == "Fictional draft"
    assert client.get(f"{url}/revisions/9").status_code == 404


def test_saving_the_same_content_does_not_create_a_version(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    url = f"/meetings/{capture_id}/minutes"
    same = client.get(url).json()
    response = client.put(url, json=same, headers={"If-Match": "1"})
    assert response.status_code == 200 and response.json()["version"] == 1


def test_an_edit_cannot_cite_a_segment_that_does_not_exist(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    bad = edited()
    bad["actions"][0]["source"] = {"segment_indices": [99]}
    response = client.put(f"/meetings/{capture_id}/minutes", json=bad, headers={"If-Match": "1"})
    assert response.status_code == 422
    assert client.get(f"/meetings/{capture_id}/minutes/meta").json()["version"] == 1


def test_validation_locks_the_minutes(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    url = f"/meetings/{capture_id}/minutes"
    assert client.post(f"{url}/validate").status_code == 428
    assert client.post(f"{url}/validate", headers={"If-Match": "5"}).status_code == 412

    validated = client.post(f"{url}/validate", headers={"If-Match": "1"})
    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert (body["status"], body["version"], body["validated_by"]) == ("validated", 2, "local-user")
    assert body["validated_at"] is not None
    assert client.get(url).headers["x-minutes-status"] == "validated"

    assert client.put(url, json=edited(), headers={"If-Match": "2"}).status_code == 409
    assert client.post(f"{url}/validate", headers={"If-Match": "2"}).status_code == 409
    assert client.get(f"{url}/meta").json()["version"] == 2

    item = client.get("/meetings").json()["items"][0]
    assert item["minutes_status"] == "validated" and item["needs_review"] is False
    statuses = [r["status"] for r in client.get(f"{url}/revisions").json()]
    assert statuses == ["draft", "validated"]


def test_validation_is_remembered_after_reopening_the_store(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    client.put(f"/meetings/{capture_id}/minutes", json=edited(), headers={"If-Match": "1"})
    client.post(f"/meetings/{capture_id}/minutes/validate", headers={"If-Match": "2"})
    reopened = SqlMeetingStore(store._engine)
    meeting = asyncio.run(reopened.get(capture_id))
    assert meeting is not None
    assert meeting.minutes_status == "validated" and meeting.minutes_version == 3
    assert [r.version for r in meeting.revisions] == [1, 2, 3]
