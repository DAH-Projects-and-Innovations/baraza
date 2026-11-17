"""Minutes contrôlées (#81-#89) : faux LLM, réparation, anti-invention."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from baraza.core.pipeline import extract_json, generate_checked_minutes
from baraza.core.segments import TranscriptSegment
from baraza.llm.client import FakeLLMClient
from baraza.llm.errors import InvalidModelOutputError


def seg(i, speaker, text, **kw):
    return TranscriptSegment(
        meeting_id="m1",
        segment_id=f"s{i}",
        speaker=speaker,
        start=float(i * 5),
        end=float(i * 5 + 4),
        text=text,
        language=kw.pop("language", "fr"),
        **kw,
    )


SEGMENTS = [
    seg(0, "Alice", "On valide le lancement de la bêta pour la fin du mois."),
    seg(1, "Alice", "Bob, tu peux envoyer le rapport avant le 15 octobre ?"),
    seg(2, "Bob", "Oui, je m'en occupe."),
]
ANSWER = json.dumps(
    {
        "summary": "Bêta validée.",
        "topics": [{"title": "Bêta", "summary": "Lancement", "source": {"segment_indices": [0]}}],
        "decisions": [
            {"text": "Lancer la bêta", "source": {"segment_indices": [0]}},
            {"text": "Inventée", "source": {"segment_indices": [9]}},
        ],
        "actions": [
            {
                "text": "Envoyer le rapport",
                "owner": "Bob",
                "due_date": "2023-10-15",
                "source": {"segment_indices": [1, 2]},
            },
            {
                "text": "Contacter le client",
                "owner": "Zoé",
                "due_date": None,
                "source": {"segment_indices": [0]},
            },
        ],
        "open_points": [],
    }
)


def transcript(segments=None):
    return SimpleNamespace(segments=SEGMENTS if segments is None else segments, language="fr")


class Scripted:
    """Faux LLM : répond dans l'ordre ; enregistre les appels."""

    model_name = "scripted-model"

    def __init__(self, *answers, error=None):
        self.answers, self.calls, self.error = list(answers), [], error

    async def complete_json(self, system, user, *, schema=None):
        self.calls.append((system, user, schema))
        if self.error:
            raise self.error
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


# ---------------- sortie JSON robuste (#82) ----------------


def test_extract_json_tolerates_fences_and_noise():
    assert extract_json('Voici :\n```json\n{"a": 1}\n```\nmerci') == {"a": 1}
    assert extract_json('blabla {"a": 1} fin') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("rien")


@pytest.mark.asyncio
async def test_valid_answer_schema_is_requested_and_checks_applied():
    llm = Scripted(ANSWER)
    minutes, corrections, version = await generate_checked_minutes(transcript(), llm)
    assert llm.calls[0][2]["properties"]["actions"]  # schéma JSON envoyé au client
    assert [d.text for d in minutes.decisions] == [
        "Lancer la bêta"
    ]  # citation hors limites rejetée
    assert minutes.actions[1].owner is None  # "Zoé" inventée
    assert {c.kind for c in corrections} == {"item_rejected", "owner_nulled"}
    assert version.startswith("fr-") and len(version) == 11


@pytest.mark.asyncio
async def test_fenced_answer_accepted():
    minutes, _, _ = await generate_checked_minutes(
        transcript(), Scripted(f"```json\n{ANSWER}\n```")
    )
    assert minutes.summary == "Bêta validée."


@pytest.mark.asyncio
async def test_invalid_json_repaired_once():
    llm = Scripted("pas du json", ANSWER)
    minutes, _, _ = await generate_checked_minutes(transcript(), llm)
    assert minutes.summary and len(llm.calls) == 2
    assert (
        "previous answer was invalid" in llm.calls[1][1]
        and "no JSON object found" in llm.calls[1][1]
    )


@pytest.mark.asyncio
async def test_schema_error_repaired_with_field_path_in_prompt():
    bad = json.dumps(
        {"summary": "s", "decisions": [{"source": {"segment_indices": [0]}}]}
    )  # "text" manquant
    llm = Scripted(bad, ANSWER)
    await generate_checked_minutes(transcript(), llm)
    assert "decisions.0.text" in llm.calls[1][1] and "Field required" in llm.calls[1][1]


@pytest.mark.asyncio
async def test_empty_segment_indices_triggers_repair_because_schema_requires_one():
    bad = json.dumps(
        {"summary": "s", "decisions": [{"text": "d", "source": {"segment_indices": []}}]}
    )
    llm = Scripted(bad, ANSWER)
    await generate_checked_minutes(transcript(), llm)
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_second_failure_gives_readable_error_after_exactly_two_calls():
    llm = Scripted("pas du json")
    with pytest.raises(InvalidModelOutputError) as err:
        await generate_checked_minutes(transcript(), llm)
    assert (
        len(llm.calls) == 2 and err.value.user_message and err.value.code == "invalid_model_output"
    )


@pytest.mark.asyncio
async def test_meeting_date_is_given_to_the_model_and_year_is_fixed():
    llm = Scripted(ANSWER)
    minutes, corrections, _ = await generate_checked_minutes(
        transcript(), llm, meeting_date=date(2026, 10, 12)
    )
    assert "Meeting date: 2026-10-12" in llm.calls[0][1]
    assert minutes.actions[0].due_date == "2026-10-15"
    assert "due_date_year_adjusted" in {c.kind for c in corrections}


@pytest.mark.asyncio
async def test_works_with_the_projects_own_fake_client():
    minutes, _, _ = await generate_checked_minutes(transcript(), FakeLLMClient(ANSWER))
    assert minutes.summary
