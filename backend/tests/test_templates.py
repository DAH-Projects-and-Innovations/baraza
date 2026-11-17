"""Minutes templates (issue #132)."""

import asyncio

from fastapi.testclient import TestClient
from test_regenerate import FIRST, SECOND, draft, generate
from test_sprint3_flow import RecordingQueue, flow, start  # noqa: F401

from baraza.core.pipeline import generate_checked_minutes
from baraza.core.templates import TEMPLATES, template_prompt
from baraza.llm.client import FakeLLMClient
from baraza.storage.sql import SqlMeetingStore

Flow = tuple[TestClient, SqlMeetingStore, RecordingQueue]


class SpyLLM(FakeLLMClient):
    def __init__(self, response: str) -> None:
        super().__init__(response)
        self.systems: list[str] = []

    async def complete_json(self, system: str, user: str, **kwargs) -> str:
        self.systems.append(system)
        return await super().complete_json(system, user, **kwargs)


def test_the_catalogue_lists_every_template_with_one_default(flow: Flow) -> None:  # noqa: F811
    client, _, _ = flow
    items = client.get("/templates").json()
    assert [t["id"] for t in items] == list(TEMPLATES)
    assert {"standard", "team_meeting", "committee", "general_assembly"} <= set(TEMPLATES)
    assert [t["id"] for t in items if t["default"]] == ["standard"]
    assert all(t["name"]["en"] and t["name"]["fr"] for t in items)


def test_every_template_has_instructions_in_both_languages_except_the_standard() -> None:
    for template in TEMPLATES.values():
        for language in ("en", "fr"):
            text = template_prompt(template.id, language)
            assert bool(text) == (template.id != "standard")
    # Anti-invention stays the rule: no template may ask to compute figures.
    assert "never" in template_prompt("general_assembly", "en")


def test_the_template_reaches_the_prompt_and_changes_its_version(flow: Flow, transcript) -> None:  # noqa: F811
    standard, committee = SpyLLM(FIRST), SpyLLM(FIRST)
    _, _, v_standard = asyncio.run(generate_checked_minutes(transcript, standard))
    _, _, v_committee = asyncio.run(
        generate_checked_minutes(transcript, committee, template="committee")
    )
    assert "committee" not in standard.systems[0].lower()
    assert "Template: committee" in committee.systems[0]
    assert v_standard != v_committee


def test_a_capture_uses_the_chosen_template_or_the_default(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    default_id = start(client)
    assert asyncio.run(store.get(default_id)).template == "standard"
    from test_sprint3_flow import REQUEST

    chosen = client.post("/captures", json={**REQUEST, "template": "committee"})
    assert chosen.status_code == 201
    assert asyncio.run(store.get(chosen.json()["capture_id"])).template == "committee"
    assert client.post("/captures", json={**REQUEST, "template": "nope"}).status_code == 422


def test_regenerating_with_another_template(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = draft(client, store)
    assert (
        client.post(
            f"/meetings/{capture_id}/minutes/regenerate", json={"template": "nope"}
        ).status_code
        == 422
    )
    response = client.post(
        f"/meetings/{capture_id}/minutes/regenerate", json={"template": "team_meeting"}
    )
    assert response.status_code == 202
    spy = SpyLLM(SECOND)
    generate(store, capture_id, spy)
    assert "Template: team meeting" in spy.systems[0]
    assert asyncio.run(store.get(capture_id)).template == "team_meeting"
