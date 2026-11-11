import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from baraza.core.meetings import InvalidMeetingTransition, MeetingStatus
from baraza.core.minute_versions import (
    MinutesConflict,
    MinutesNotFound,
    MinutesService,
    ValidatedMinutesImmutable,
)
from baraza.core.minutes import Minutes
from baraza.db.migrations import upgrade_database
from baraza.db.session import Database
from baraza.storage.captures import SqlCaptureStore


@pytest.fixture
async def minutes_db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'minutes.db'}")
    await upgrade_database(database.engine)
    meetings = SqlCaptureStore(database.engine)
    await meetings.create("m1")
    await meetings.transition("m1", MeetingStatus.PROCESSING)
    try:
        yield database, meetings
    finally:
        await database.dispose()


async def draft(sessions: async_sessionmaker):
    async with sessions() as session, session.begin():
        return await MinutesService(session).create_draft(
            "m1",
            Minutes(summary="Fictional draft"),
            actor="generator",
            template="standard",
            model_name="fake-model",
            prompt_version="v1",
        )


async def test_draft_edit_validate_and_immutable_history(minutes_db):
    database, meetings = minutes_db
    created = await draft(database.sessions)
    assert created.version == 1
    assert created.status == "draft"
    assert created.validated_by is None
    assert (await meetings.get("m1")).status == "draft_ready"
    async with database.sessions() as session, session.begin():
        saved = await MinutesService(session).save_draft(
            "m1",
            Minutes(summary="Fictional corrected draft"),
            actor="editor",
            expected_version=1,
        )
        assert saved.version == 2
    async with database.sessions() as session, session.begin():
        validated = await MinutesService(session).validate(
            "m1", actor="reviewer", expected_version=2
        )
        assert validated.version == 3
        assert validated.validated_by == "reviewer"
        assert validated.validated_at.utcoffset().total_seconds() == 0
    assert (await meetings.get("m1")).status == "validated"
    async with database.sessions() as session, session.begin():
        service = MinutesService(session)
        with pytest.raises(ValidatedMinutesImmutable):
            await service.save_draft(
                "m1", Minutes(summary="Forbidden"), actor="editor", expected_version=3
            )
        with pytest.raises(ValidatedMinutesImmutable):
            await service.validate("m1", actor="reviewer", expected_version=3)
        assert await service.get("m1") == validated
        history = await service.revisions("m1")
        assert [r.version for r in history] == [1, 2, 3]
        assert [r.saved_by for r in history] == ["generator", "editor", "reviewer"]
        assert [r.status for r in history] == ["draft", "draft", "validated"]
        assert [r.content.summary for r in history] == [
            "Fictional draft",
            "Fictional corrected draft",
            "Fictional corrected draft",
        ]
        assert all(r.model_name == "fake-model" and r.prompt_version == "v1" for r in history)


async def test_stale_save_and_validation_leave_current_version_unchanged(minutes_db):
    database, meetings = minutes_db
    await draft(database.sessions)
    async with database.sessions() as session, session.begin():
        service = MinutesService(session)
        saved = await service.save_draft(
            "m1", Minutes(summary="New"), actor="first", expected_version=1
        )
        with pytest.raises(MinutesConflict, match="Stale"):
            await service.save_draft(
                "m1", Minutes(summary="Stale"), actor="second", expected_version=1
            )
        with pytest.raises(MinutesConflict, match="Stale"):
            await service.validate("m1", actor="second", expected_version=1)
        assert await service.get("m1") == saved
        assert len(await service.revisions("m1")) == 2
    assert (await meetings.get("m1")).status == "draft_ready"


async def test_duplicate_draft_does_not_replace_content(minutes_db):
    database, _ = minutes_db
    created = await draft(database.sessions)
    with pytest.raises(MinutesConflict):
        await draft(database.sessions)
    async with database.sessions() as session:
        assert await MinutesService(session).get("m1") == created
        assert len(await MinutesService(session).revisions("m1")) == 1


async def test_invalid_meeting_transition_rolls_back_minutes_and_revision(minutes_db):
    database, meetings = minutes_db
    await draft(database.sessions)
    await meetings.transition("m1", MeetingStatus.ERROR)
    async with database.sessions() as session, session.begin():
        service = MinutesService(session)
        with pytest.raises(InvalidMeetingTransition):
            await service.validate("m1", actor="reviewer", expected_version=1)
        assert (await service.get("m1")).status == "draft"
        assert (await service.get("m1")).version == 1
        assert len(await service.revisions("m1")) == 1
    assert (await meetings.get("m1")).status == "error"


async def test_missing_meeting_cannot_create_orphan_minutes(minutes_db):
    database, _ = minutes_db
    async with database.sessions() as session, session.begin():
        service = MinutesService(session)
        with pytest.raises(MinutesNotFound):
            await service.create_draft(
                "missing",
                Minutes(summary="Draft"),
                actor="generator",
                template="standard",
                model_name="fake",
                prompt_version="v1",
            )
        with pytest.raises(MinutesNotFound):
            await service.get("missing")


async def test_outer_rollback_removes_draft_and_business_transition(minutes_db):
    database, meetings = minutes_db
    async with database.sessions() as session:
        await session.begin()
        await MinutesService(session).create_draft(
            "m1",
            Minutes(summary="Rolled back"),
            actor="generator",
            template="standard",
            model_name="fake",
            prompt_version="v1",
        )
        await session.rollback()
    async with database.sessions() as session:
        with pytest.raises(MinutesNotFound):
            await MinutesService(session).get("m1")
    assert (await meetings.get("m1")).status == "processing"


@pytest.mark.parametrize("actor", ["", " ", "x" * 201])
async def test_revision_actor_is_required(minutes_db, actor):
    database, _ = minutes_db
    await draft(database.sessions)
    async with database.sessions() as session, session.begin():
        with pytest.raises(ValueError, match="Actor"):
            await MinutesService(session).save_draft(
                "m1", Minutes(summary="New"), actor=actor, expected_version=1
            )
        assert len(await MinutesService(session).revisions("m1")) == 1
