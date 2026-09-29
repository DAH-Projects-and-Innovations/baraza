import json

import pytest

from baraza.core.generation import generate_minutes, load_prompt
from baraza.core.minutes import ActionItem, SourceRef
from baraza.core.transcript import Transcript
from baraza.llm.client import FakeLLMClient

FAKE_RESPONSE = json.dumps(
    {
        "summary": "The team moves the launch to March.",
        "decisions": [{"text": "Launch moved to March.", "source": {"segment_indices": [2]}}],
        "actions": [
            {
                "text": "Prepare the backward plan",
                "owner": "Koffi Test",
                "due_date": "Friday",
                "source": {"segment_indices": [2, 3]},
            }
        ],
        "open_points": [{"text": "Review the budget", "source": {"segment_indices": [4]}}],
    }
)


def test_transcript_fixture_is_valid(transcript: Transcript) -> None:
    assert transcript.schema_version == "1.0"
    assert len(transcript.segments) == 5


async def test_generate_minutes_with_fake_llm(transcript: Transcript) -> None:
    llm = FakeLLMClient(FAKE_RESPONSE)
    minutes = await generate_minutes(transcript, llm)

    assert minutes.decisions[0].text == "Launch moved to March."
    assert minutes.actions[0].owner == "Koffi Test"
    system, user = llm.calls[0]
    assert "Never invent" in system
    assert "[4] Speaker 3" in user


def test_missing_owner_and_due_date_are_none() -> None:
    item = ActionItem(text="x", source=SourceRef(segment_indices=[0]))
    assert item.owner is None
    assert item.due_date is None


@pytest.mark.parametrize("language", ["en", "fr"])
def test_prompt_exists_for_supported_languages(language: str) -> None:
    assert "segment_indices" in load_prompt("minutes", language)
