"""Tests d'intégration du job de génération (issue #89) : faux LLM + dépôt en mémoire."""
import json
import logging
from datetime import date

import pytest

from app.llm.client import LLMSettings
from app.llm.errors import QuotaExceededError
from app.minutes.generation import (
    DEFAULT_TEMPLATE, STATUS_DRAFT_READY, STATUS_GENERATING, STATUS_GENERATION_FAILED,
    run_generation,
)
from app.minutes.prompts import PROMPT_VERSION
from app.minutes.schema import Segment, Transcript
from app.minutes.testing import InMemoryRepository, RecordingNotifier
from app.minutes.worker import generate_minutes_job


class FakeLLM:
    settings = LLMSettings(base_url="http://fake", model="fake-model")

    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.calls = answer, error, []

    async def complete(self, messages, **kwargs):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.answer


ANSWER = json.dumps({
    "title": "Point projet", "summary": "RAS",
    "decisions": [{"text": "Inventée", "segment_indices": [9]}],
    "action_items": [{"description": "Envoyer le rapport", "owner": "Zoé",
                      "due_date": "2026-10-15", "segment_indices": [0]}],
})


def transcript(**kw):
    base = dict(
        meeting_id="m1",
        segments=[Segment(1, "Ok.", "spk_2"),   # volontairement dans le désordre
                  Segment(0, "Bob enverra le rapport avant le 15 octobre.", "spk_1")],
        participants=["spk_1", "spk_2"],
        speaker_renames={"spk_1": "Alice", "spk_2": "Bob"},
    )
    base.update(kw)
    return Transcript(**base)


async def run(repo=None, llm=None, notifier=None, **kw):
    repo = repo or InMemoryRepository(transcript())
    llm = llm or FakeLLM(ANSWER)
    notifier = notifier or RecordingNotifier()
    result = await run_generation("m1", repo=repo, client=llm, notifier=notifier, **kw)
    return result, repo, llm, notifier


# ---------------- critère d'acceptation : transcription -> draft_ready ----------------

async def test_transcript_to_draft_ready():
    result, repo, _, notifier = await run()
    assert result.status == "draft_ready" and result.draft_id == "draft-1"
    assert repo.status == STATUS_DRAFT_READY
    assert repo.status_history == [STATUS_GENERATING, STATUS_DRAFT_READY]
    draft = repo.drafts[0]
    assert draft.model == "fake-model" and draft.prompt_version == PROMPT_VERSION
    assert notifier.sent == ["m1"]


async def test_anti_invention_is_applied_before_storing():
    _, repo, _, _ = await run()
    draft = repo.drafts[0]
    assert draft.minutes.decisions == []                    # citation hors limites
    assert repo.action_items[0].owner is None               # "Zoé" inventée
    assert repo.action_items[0].due_date == "2026-10-15"    # retrouvée dans le segment
    assert {c.kind for c in draft.corrections} == {"item_rejected", "owner_nulled"}


async def test_speaker_renames_are_applied_and_segments_sorted():
    _, _, llm, _ = await run()
    prompt = llm.calls[0][1]["content"]
    assert "Alice" in prompt and "spk_1" not in prompt
    assert prompt.index("[0]") < prompt.index("[1]")        # segments triés par index


async def test_missing_template_uses_default():
    _, _, llm, _ = await run(repo=InMemoryRepository(transcript(), template=None))
    assert DEFAULT_TEMPLATE in llm.calls[0][1]["content"]


async def test_year_invented_by_model_is_fixed_using_meeting_date():
    answer = json.dumps({"title": "T", "summary": "S", "decisions": [],
        "action_items": [{"description": "Rapport", "owner": "Alice",
                          "due_date": "2023-10-15", "segment_indices": [0]}]})
    repo = InMemoryRepository(transcript(meeting_date=date(2026, 10, 12)))
    await run(repo=repo, llm=FakeLLM(answer))
    assert repo.action_items[0].due_date == "2026-10-15"
    assert [c.kind for c in repo.drafts[0].corrections] == ["due_date_year_adjusted"]


# ---------------- échecs : message lisible, rien d'enregistré ----------------

async def test_llm_failure_sets_failed_status():
    result, repo, _, notifier = await run(llm=FakeLLM(error=QuotaExceededError()))
    assert result.status == "failed" and result.error_code == "quota_exceeded"
    assert repo.status == STATUS_GENERATION_FAILED and repo.reason
    assert repo.drafts == [] and notifier.sent == []


async def test_invalid_json_after_repair_sets_readable_error():
    result, repo, llm, _ = await run(llm=FakeLLM("pas du json"))
    assert result.error_code == "invalid_model_output"
    assert len(llm.calls) == 2                               # 1 appel + 1 réparation
    assert repo.status == STATUS_GENERATION_FAILED


async def test_empty_transcript_fails_without_calling_llm():
    result, repo, llm, _ = await run(repo=InMemoryRepository(transcript(segments=[])))
    assert result.error_code == "empty_transcript" and llm.calls == []
    assert repo.status == STATUS_GENERATION_FAILED


async def test_storage_error_rolls_back_and_is_reraised_for_retry():
    repo = InMemoryRepository(transcript())
    repo.fail_on_create_action_items = RuntimeError("db down")
    with pytest.raises(RuntimeError):
        await run(repo=repo)
    assert repo.drafts == [] and repo.action_items == []     # rollback : pas de brouillon orphelin
    assert repo.status == STATUS_GENERATION_FAILED


async def test_notification_failure_does_not_undo_the_draft():
    result, repo, _, _ = await run(notifier=RecordingNotifier(fail=True))
    assert result.status == "draft_ready" and repo.status == STATUS_DRAFT_READY


# ---------------- reprise / idempotence (issue #60) ----------------

async def test_already_draft_ready_is_skipped():
    repo = InMemoryRepository(transcript(), status=STATUS_DRAFT_READY)
    result, _, llm, notifier = await run(repo=repo)
    assert result.status == "skipped" and llm.calls == [] and repo.drafts == [] and notifier.sent == []


async def test_force_regenerates():
    repo = InMemoryRepository(transcript(), status=STATUS_DRAFT_READY)
    result, _, llm, _ = await run(repo=repo, force=True)
    assert result.status == "draft_ready" and len(llm.calls) == 1


async def test_retry_after_failure_succeeds_once():
    repo = InMemoryRepository(transcript())
    await run(repo=repo, llm=FakeLLM(error=QuotaExceededError()))
    result, _, _, notifier = await run(repo=repo)            # relance du job
    assert result.status == "draft_ready" and len(repo.drafts) == 1 and notifier.sent == ["m1"]


# ---------------- confidentialité et branchement arq ----------------

async def test_job_never_logs_transcript_content(caplog):
    caplog.set_level(logging.DEBUG)
    repo = InMemoryRepository(transcript(segments=[Segment(0, "SECRET-SENTENCE", "spk_1")]))
    await run(repo=repo, llm=FakeLLM(error=QuotaExceededError()))
    await run(repo=InMemoryRepository(transcript(segments=[Segment(0, "SECRET-SENTENCE", "spk_1")])))
    assert "SECRET-SENTENCE" not in caplog.text


async def test_arq_job_function_returns_a_serializable_summary():
    ctx = {"repo": InMemoryRepository(transcript()), "llm": FakeLLM(ANSWER), "notifier": RecordingNotifier()}
    out = await generate_minutes_job(ctx, "m1")
    assert out == {"status": "draft_ready", "draft_id": "draft-1", "error_code": None}
