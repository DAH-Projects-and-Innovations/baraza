"""Naming the speakers a capture could not name (issue #138)."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from test_sprint3_flow import RecordingQueue, flow, start  # noqa: F401

from baraza.core.speakers import InvalidSpeakerName, clean_name, is_unnamed
from baraza.llm.client import FakeLLMClient
from baraza.storage.sql import SqlMeetingStore
from baraza.worker import generate_minutes_task

Flow = tuple[TestClient, SqlMeetingStore, RecordingQueue]

# The fictional demo transcript has three speakers; the third one is "Speaker 3".
DRAFT = (
    '{"summary":"Fictional draft","actions":['
    '{"text":"Review the budget","owner":"Speaker 3","due_date":null,'
    '"source":{"segment_indices":[2]}},'
    '{"text":"Send the plan","owner":"Awa Example","due_date":null,'
    '"source":{"segment_indices":[0]}}]}'
)


def meeting_with_draft(client: TestClient, store: SqlMeetingStore) -> str:
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    llm = FakeLLMClient(DRAFT)
    asyncio.run(generate_minutes_task({"meeting_store": store, "llm": llm}, capture_id))
    return capture_id


def speakers(client: TestClient, capture_id: str) -> list[str]:
    return [s["speaker"] for s in client.get(f"/meetings/{capture_id}/segments").json()]


def rename(client: TestClient, capture_id: str, old: str, new: str):
    return client.post(
        f"/meetings/{capture_id}/speakers/rename", json={"from_name": old, "to_name": new}
    )


def test_a_name_is_applied_to_every_line_of_the_speaker(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    assert "Speaker 3" in speakers(client, capture_id)

    response = rename(client, capture_id, "Speaker 3", "  Nadia   M. ")
    assert response.status_code == 200, response.text
    assert response.json()["renamed_segments"] >= 1
    assert "Speaker 3" not in speakers(client, capture_id)
    assert "Nadia M." in speakers(client, capture_id)  # extra spaces are tidied
    # The transcript kept with the meeting agrees with the segments.
    transcript = client.get(f"/meetings/{capture_id}/transcript").json()
    assert "Speaker 3" not in [s["speaker"] for s in transcript["segments"]]
    assert "Nadia M." in [s["speaker"] for s in transcript["segments"]]


def test_the_drafts_action_owners_follow_and_make_a_new_version(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    before = client.get(f"/meetings/{capture_id}/minutes/meta").json()["version"]

    result = rename(client, capture_id, "Speaker 3", "Nadia M.").json()
    assert result["minutes_version"] == before + 1

    actions = client.get(f"/meetings/{capture_id}/minutes").json()["actions"]
    assert [a["owner"] for a in actions] == ["Nadia M.", "Awa Example"]
    revisions = client.get(f"/meetings/{capture_id}/minutes/revisions").json()
    assert revisions[-1]["version"] == before + 1 and revisions[-1]["saved_by"] == "local-user"
    original = client.get(f"/meetings/{capture_id}/minutes/revisions/1").json()
    assert original["actions"][0]["owner"] == "Speaker 3"  # the assistant's text is kept


def test_a_name_that_changes_no_owner_does_not_touch_the_minutes(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    before = client.get(f"/meetings/{capture_id}/minutes/meta").json()["version"]
    result = rename(client, capture_id, "Koffi Test", "Koffi T.").json()
    assert result["minutes_version"] is None
    assert client.get(f"/meetings/{capture_id}/minutes/meta").json()["version"] == before


def test_unknown_blank_and_identical_names_are_refused(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    assert rename(client, capture_id, "Nobody", "Someone").status_code == 404
    assert rename(client, capture_id, "Speaker 3", "   ").status_code == 422
    assert rename(client, capture_id, "Speaker 3", "x" * 201).status_code == 422
    assert rename(client, capture_id, "Speaker 3", "Speaker 3").status_code == 422
    assert rename(client, capture_id, "Speaker 3", "bad\x00name").status_code == 422
    assert "Speaker 3" in speakers(client, capture_id)


def test_two_labels_can_be_merged_into_one_person(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    assert rename(client, capture_id, "Speaker 3", "Awa Example").status_code == 200
    assert set(speakers(client, capture_id)) == {"Awa Example", "Koffi Test"}


def test_validated_minutes_lock_their_speakers(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = meeting_with_draft(client, store)
    version = client.get(f"/meetings/{capture_id}/minutes/meta").json()["version"]
    client.post(f"/meetings/{capture_id}/minutes/validate", headers={"If-Match": str(version)})
    assert rename(client, capture_id, "Speaker 3", "Nadia M.").status_code == 409
    assert "Speaker 3" in speakers(client, capture_id)


def test_renaming_before_the_minutes_exist_only_renames_the_transcript(flow: Flow) -> None:  # noqa: F811
    client, _, _ = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    response = rename(client, capture_id, "Speaker 3", "Nadia M.")
    assert response.status_code == 200
    assert response.json()["minutes_version"] is None


def test_the_name_rules() -> None:
    assert clean_name("  Awa \t Example ") == "Awa Example"
    for bad in ["", "   ", "x" * 201, "a\x07b"]:
        with pytest.raises(InvalidSpeakerName):
            clean_name(bad)
    assert is_unnamed("Speaker 12") and not is_unnamed("Speaker Twelve")
    assert not is_unnamed("Awa Example") and not is_unnamed("speaker 3")
