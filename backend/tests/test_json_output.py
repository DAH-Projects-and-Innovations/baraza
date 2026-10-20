import json

import pytest

from app.llm.errors import InvalidModelOutputError
from app.minutes.json_output import describe_error, extract_json, generate_minutes_json

VALID = '{"title":"T","summary":"S","decisions":[{"text":"D","segment_indices":[0]}],"action_items":[]}'
MISSING_TEXT = '{"decisions": [{"segment_indices": [0]}]}'  # champ "text" manquant


class ScriptedLLM:
    def __init__(self, *answers):
        self.answers, self.calls, self.kwargs = list(answers), [], []

    async def complete(self, messages, **kwargs):
        self.calls.append(messages)
        self.kwargs.append(kwargs)
        return self.answers.pop(0)


def test_extract_json_handles_fences_and_noise():
    assert extract_json('Voici:\n```json\n{"a": 1}\n```\nmerci') == {"a": 1}
    assert extract_json('blabla {"a": 1} fin') == {"a": 1}


def test_extract_json_without_object():
    with pytest.raises(ValueError):
        extract_json("rien")


async def test_valid_output_and_schema_is_requested():
    llm = ScriptedLLM(VALID)
    m = await generate_minutes_json(llm, [])
    assert m.decisions[0].text == "D"
    assert llm.kwargs[0]["json_mode"] is True
    assert "action_items" in llm.kwargs[0]["json_schema"]["properties"]


async def test_fenced_output_is_accepted():
    m = await generate_minutes_json(ScriptedLLM(f"```json\n{VALID}\n```"), [])
    assert m.title == "T"


async def test_invalid_json_is_repaired_once():
    llm = ScriptedLLM("pas du json", VALID)
    m = await generate_minutes_json(llm, [{"role": "user", "content": "x"}])
    assert m.title == "T" and len(llm.calls) == 2
    repair = llm.calls[1][-1]["content"]
    assert "invalid" in repair.lower() and "JSON" in repair


async def test_schema_error_is_repaired_with_validation_error_in_prompt():
    llm = ScriptedLLM(MISSING_TEXT, VALID)
    m = await generate_minutes_json(llm, [])
    assert m.decisions[0].text == "D"
    repair = llm.calls[1][-1]["content"]
    assert "decisions.0.text" in repair          # le chemin du champ fautif
    assert "Field required" in repair            # le message Pydantic


async def test_second_failure_raises_readable_error_after_exactly_two_calls():
    llm = ScriptedLLM(MISSING_TEXT, MISSING_TEXT)
    with pytest.raises(InvalidModelOutputError) as err:
        await generate_minutes_json(llm, [])
    assert len(llm.calls) == 2                    # un seul réessai
    assert err.value.user_message                 # message lisible
    assert err.value.code == "invalid_model_output"


def test_describe_error_never_echoes_received_values():
    from pydantic import ValidationError

    from app.minutes.schema import Minutes

    try:
        Minutes.model_validate({"decisions": [{"text": "TOP-SECRET", "segment_indices": ["x"]}]})
    except ValidationError as exc:
        assert "TOP-SECRET" not in describe_error(exc)
