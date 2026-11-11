"""Pipeline de génération (#81-#89) : faux LLM, dépôt en mémoire, puis vraie base SQLite."""

import asyncio
import json
import logging
from datetime import date

import pytest
import pytest_asyncio
from baraza.core.segments import TranscriptSegment
from baraza.storage.sql import SqlSegmentStore
from minutes_fakes import MemRepo, Notifier
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.core.pipeline import (
    STATUS_DRAFT_READY,
    STATUS_GENERATING,
    STATUS_GENERATION_FAILED,
    LoadedTranscript,
    extract_json,
    generate_checked_minutes,
    run_generation,
)
from baraza.llm.client import FakeLLMClient
from baraza.llm.errors import InvalidModelOutputError, QuotaExceededError
from baraza.storage.minutes_sql import DraftActionItemRow, SqlMinutesRepository


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


def transcript(segments=None, **kw):
    return LoadedTranscript(
        meeting_id="m1", segments=SEGMENTS if segments is None else segments, language="fr", **kw
    )


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


# ---------------- job de bout en bout (#89), dépôt en mémoire ----------------


async def run(repo=None, llm=None, notifier=None, **kw):
    repo, llm, notifier = (
        repo or MemRepo(transcript()),
        llm or Scripted(ANSWER),
        notifier or Notifier(),
    )
    return (
        await run_generation("m1", repo=repo, llm=llm, notifier=notifier, **kw),
        repo,
        llm,
        notifier,
    )


@pytest.mark.asyncio
async def test_transcript_to_draft_ready():
    result, repo, _, notifier = await run()
    assert result.status == "draft_ready" and result.draft_id == 1
    assert repo.history == [STATUS_GENERATING, STATUS_DRAFT_READY]
    d = repo.drafts[0]
    assert d.model == "scripted-model" and d.prompt_version.startswith("fr-")
    assert [a.owner for a in repo.items] == ["Bob", None]
    assert notifier.sent == ["m1"]


@pytest.mark.asyncio
async def test_llm_error_sets_failed_status_without_draft_or_notification():
    result, repo, _, notifier = await run(llm=Scripted(ANSWER, error=QuotaExceededError()))
    assert result.status == "failed" and result.error_code == "quota_exceeded"
    assert repo.status == STATUS_GENERATION_FAILED and repo.reason
    assert repo.drafts == [] and notifier.sent == []


@pytest.mark.asyncio
async def test_invalid_output_after_repair_sets_readable_error():
    result, repo, llm, _ = await run(llm=Scripted("pas du json"))
    assert result.error_code == "invalid_model_output" and len(llm.calls) == 2
    assert repo.status == STATUS_GENERATION_FAILED


@pytest.mark.asyncio
async def test_empty_transcript_fails_without_calling_llm():
    result, _repo, llm, _ = await run(repo=MemRepo(transcript(segments=[])))
    assert result.error_code == "empty_transcript" and llm.calls == []


@pytest.mark.asyncio
async def test_storage_error_rolls_back_and_is_reraised_for_arq_retry():
    repo = MemRepo(transcript())
    repo.fail_on_items = RuntimeError("db down")
    with pytest.raises(RuntimeError):
        await run(repo=repo)
    assert repo.drafts == [] and repo.items == [] and repo.status == STATUS_GENERATION_FAILED


@pytest.mark.asyncio
async def test_notification_failure_keeps_the_draft():
    result, repo, _, _ = await run(notifier=Notifier(fail=True))
    assert result.status == "draft_ready" and repo.status == STATUS_DRAFT_READY


@pytest.mark.asyncio
async def test_already_draft_ready_is_skipped_and_force_regenerates():
    repo = MemRepo(transcript(), status=STATUS_DRAFT_READY)
    result, _, llm, _ = await run(repo=repo)
    assert result.status == "skipped" and llm.calls == [] and repo.drafts == []
    result, _, llm, _ = await run(repo=repo, force=True)
    assert result.status == "draft_ready" and len(llm.calls) == 1


@pytest.mark.asyncio
async def test_retry_after_failure_succeeds_once():
    repo = MemRepo(transcript())
    await run(repo=repo, llm=Scripted(ANSWER, error=QuotaExceededError()))
    result, _, _, notifier = await run(repo=repo)
    assert result.status == "draft_ready" and len(repo.drafts) == 1 and notifier.sent == ["m1"]


@pytest.mark.asyncio
async def test_job_never_logs_transcript_content(caplog):
    caplog.set_level(logging.DEBUG)
    secret = transcript(segments=[seg(0, "Alice", "SECRET-SENTENCE")])
    await run(repo=MemRepo(secret), llm=Scripted(ANSWER, error=QuotaExceededError()))
    await run(repo=MemRepo(secret), llm=Scripted("pas du json"))
    await run(repo=MemRepo(secret))
    assert "SECRET-SENTENCE" not in caplog.text


# ---------------- vraie base SQLite : segments -> job -> brouillon ----------------


@pytest_asyncio.fixture
async def sql_repo(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    repo = SqlMinutesRepository(engine)
    await SqlSegmentStore(engine).upsert([*SEGMENTS, seg(3, "Bob", "partiel...", is_final=False)])
    yield repo, engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_end_to_end_from_stored_segments(sql_repo):
    repo, engine = sql_repo
    result = await run_generation("m1", repo=repo, llm=Scripted(ANSWER), notifier=Notifier())
    assert result.status == "draft_ready"
    assert await repo.get_state("m1") == ("draft_ready", None)
    draft = await repo.get_latest_draft("m1")
    assert draft["model"] == "scripted-model" and draft["minutes"]["summary"] == "Bêta validée."
    assert [c["kind"] for c in draft["corrections"]] == ["item_rejected", "owner_nulled"]
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with async_sessionmaker(engine)() as s:
        rows = (await s.scalars(select(DraftActionItemRow).order_by(DraftActionItemRow.id))).all()
    assert [(r.text, r.owner, r.draft_id) for r in rows] == [
        ("Envoyer le rapport", "Bob", draft["id"]),
        ("Contacter le client", None, draft["id"]),
    ]


@pytest.mark.asyncio
async def test_sql_non_final_segments_are_ignored(sql_repo):
    repo, _ = sql_repo
    loaded = await repo.load_transcript("m1")
    assert len(loaded.segments) == 3 and loaded.language == "fr"


@pytest.mark.asyncio
async def test_sql_second_run_is_skipped_without_duplicates(sql_repo):
    repo, _ = sql_repo
    await run_generation("m1", repo=repo, llm=Scripted(ANSWER), notifier=Notifier())
    again = await run_generation("m1", repo=repo, llm=Scripted(ANSWER), notifier=Notifier())
    assert again.status == "skipped"


@pytest.mark.asyncio
async def test_sql_transaction_rolls_back_draft_when_actions_fail(sql_repo):
    repo, _ = sql_repo

    class Boom(SqlMinutesRepository):
        async def create_action_items(self, *a, **k):
            raise RuntimeError("db down")

    boom = Boom(repo._engine)
    with pytest.raises(RuntimeError):
        await run_generation("m1", repo=boom, llm=Scripted(ANSWER), notifier=Notifier())
    assert await repo.get_latest_draft("m1") is None  # pas de brouillon orphelin
    assert (await repo.get_state("m1"))[0] == "generation_failed"


@pytest.mark.asyncio
async def test_sql_two_meetings_in_parallel_do_not_mix(sql_repo):
    repo, engine = sql_repo
    store = SqlSegmentStore(engine)
    await store.upsert(
        [
            TranscriptSegment(
                meeting_id="m2",
                segment_id="a",
                speaker="Bob",
                start=0.0,
                end=1.0,
                text="Bob enverra le rapport avant le 15 octobre.",
                language="fr",
            )
        ]
    )
    a, b = await asyncio.gather(
        run_generation("m1", repo=repo, llm=Scripted(ANSWER), notifier=Notifier()),
        run_generation("m2", repo=repo, llm=Scripted(ANSWER), notifier=Notifier()),
    )
    assert a.status == b.status == "draft_ready"
    assert (await repo.get_latest_draft("m1"))["id"] != (await repo.get_latest_draft("m2"))["id"]
