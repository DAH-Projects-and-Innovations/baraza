import asyncio
import os
from uuid import uuid4

import pytest
import respx
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import text

from alembic import command
from baraza.adapters.vexa import VexaAdapter
from baraza.config import Settings
from baraza.core.captures import VexaCaptureService
from baraza.core.meetings import MeetingStatus, Transition
from baraza.core.minute_versions import MinutesConflict, MinutesService, ValidatedMinutesImmutable
from baraza.core.minutes import Minutes
from baraza.db.migrations import migration_config
from baraza.storage.captures import MeetingRow, SqlCaptureStore
from baraza.storage.sql import SqlSegmentStore
from baraza.vexa.client import VexaClient

pytestmark = pytest.mark.integration


async def test_real_postgres_session_select_one(postgres_session):
    assert await postgres_session.scalar(text("SELECT 1")) == 1


async def test_postgres_jsonb_schema_has_no_pending_migrations(postgres_database):
    async with postgres_database.engine.begin() as connection:
        assert (
            await connection.scalar(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'minutes' AND column_name = 'content'"
                )
            )
            == "jsonb"
        )

        def check(sync_connection):
            config = migration_config()
            config.attributes["connection"] = sync_connection
            command.check(config)

        await connection.run_sync(check)


async def test_real_postgres_minutes_lifecycle(postgres_session):
    initial = Transition(from_status=None, to_status="processing")
    postgres_session.add(
        MeetingRow(
            id="pg-lifecycle",
            status="processing",
            version=0,
            transitions=[initial.model_dump(mode="json")],
            updated_at=initial.at,
        )
    )
    await postgres_session.flush()
    service = MinutesService(postgres_session)
    created = await service.create_draft(
        "pg-lifecycle",
        Minutes(summary="Draft"),
        actor="generator",
        template="standard",
        model_name="fake",
        prompt_version="v1",
    )
    saved = await service.save_draft(
        "pg-lifecycle", Minutes(summary="Edited"), actor="editor", expected_version=created.version
    )
    validated = await service.validate(
        "pg-lifecycle", actor="reviewer", expected_version=saved.version
    )
    assert validated.validated_at.utcoffset().total_seconds() == 0
    with pytest.raises(ValidatedMinutesImmutable):
        await service.save_draft(
            "pg-lifecycle",
            Minutes(summary="Forbidden"),
            actor="editor",
            expected_version=validated.version,
        )
    assert (await service.get("pg-lifecycle")).content.summary == "Edited"
    assert len(await service.revisions("pg-lifecycle")) == 3


async def test_concurrent_postgres_edits_allow_only_one_writer(postgres_database):
    meeting_id = str(uuid4())
    store = SqlCaptureStore(postgres_database.engine)
    await store.create(meeting_id)
    await store.transition(meeting_id, MeetingStatus.PROCESSING)
    async with postgres_database.sessions() as session, session.begin():
        await MinutesService(session).create_draft(
            meeting_id,
            Minutes(summary="Draft"),
            actor="generator",
            template="standard",
            model_name="fake",
            prompt_version="v1",
        )

    async def edit(actor):
        async with postgres_database.sessions() as session, session.begin():
            return await MinutesService(session).save_draft(
                meeting_id, Minutes(summary=actor), actor=actor, expected_version=1
            )

    results = await asyncio.gather(edit("editor-one"), edit("editor-two"), return_exceptions=True)
    assert sum(isinstance(r, MinutesConflict) for r in results) == 1
    assert sum(not isinstance(r, Exception) for r in results) == 1
    async with postgres_database.sessions() as session:
        assert (await MinutesService(session).get(meeting_id)).version == 2
        assert len(await MinutesService(session).revisions(meeting_id)) == 2


async def test_real_redis_connection():
    url = os.environ.get("BARAZA_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set BARAZA_TEST_REDIS_URL to run the real Redis integration test")
    redis = await create_pool(RedisSettings.from_dsn(url))
    try:
        assert await redis.ping()
    finally:
        await redis.aclose()


@respx.mock
async def test_vexa_polling_uses_migrated_postgres_and_is_idempotent(postgres_database):
    settings = Settings(_env_file=None, vexa_api_key="fictional-key", vexa_retries=0)
    client = VexaClient(settings)
    captures = SqlCaptureStore(postgres_database.engine)
    segments = SqlSegmentStore(postgres_database.engine)
    service = VexaCaptureService(VexaAdapter(client, settings), captures, segments)
    meeting_id = str(uuid4())
    bot = {
        "id": 42,
        "platform": "google_meet",
        "native_meeting_id": "abc-defg-hij",
        "status": "requested",
    }
    base = settings.vexa_base_url
    respx.post(f"{base}/bots").respond(201, json=bot)
    state = respx.get(f"{base}/meetings/42").respond(200, json={**bot, "status": "active"})
    transcript = respx.get(f"{base}/transcripts/by-id/42").respond(
        200,
        json={
            **bot,
            "status": "active",
            "segments": [{"segment_id": "s1", "start": 0, "end": 1, "text": "Fictional segment"}],
        },
    )
    try:
        await service.start(meeting_id, "https://meet.google.com/abc-defg-hij")
        capture = (await captures.captures())[0]
        await service.poll(capture)
        assert (await captures.get(meeting_id)).status == "capturing"
        state.respond(200, json={**bot, "status": "completed"})
        transcript.respond(
            200,
            json={
                **bot,
                "status": "completed",
                "segments": [
                    {"segment_id": "s1", "start": 0, "end": 1, "text": "Fictional segment"}
                ],
            },
        )
        await service.poll(capture)
        history = (await captures.get(meeting_id)).transitions
        await service.poll(capture)
        assert (await captures.get(meeting_id)).status == "processing"
        assert (await captures.get(meeting_id)).transitions == history
        assert len(await segments.list(meeting_id)) == 1
        assert await captures.captures() == []
    finally:
        await client.aclose()
