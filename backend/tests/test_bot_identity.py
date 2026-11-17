"""The visible name of the assistant is shown to the organizer (issue #128)."""

from fastapi.testclient import TestClient
from test_sprint3_flow import RecordingQueue, flow, start  # noqa: F401

from baraza.config import get_settings
from baraza.storage.sql import SqlMeetingStore

Flow = tuple[TestClient, SqlMeetingStore, RecordingQueue]


def test_the_organizer_can_read_the_name_the_bot_will_show(flow: Flow) -> None:  # noqa: F811
    client, _, _ = flow
    response = client.get("/captures/bot")
    assert response.status_code == 200
    assert response.json() == {"name": get_settings().vexa_bot_name}
    assert "note taker" in response.json()["name"]


def test_the_bot_route_does_not_swallow_capture_ids(flow: Flow) -> None:  # noqa: F811
    client, _, _ = flow
    capture_id = start(client)
    assert client.get(f"/captures/{capture_id}").json()["capture_id"] == capture_id
    assert client.get("/captures/unknown").status_code == 404
