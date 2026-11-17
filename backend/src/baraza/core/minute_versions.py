"""Transactional minutes editing, optimistic locking and explicit validation."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from baraza.core.meetings import MeetingStatus, Transition, check_transition
from baraza.core.minutes import Minutes
from baraza.storage.captures import MeetingRow
from baraza.storage.minutes import MinutesRevisionRow, MinutesRow


class MinutesNotFound(ValueError):
    pass


class MinutesConflict(ValueError):
    pass


class ValidatedMinutesImmutable(MinutesConflict):
    pass


class StoredMinutes(BaseModel):
    meeting_id: str
    status: Literal["draft", "validated"]
    content: Minutes
    template: str
    model_name: str
    prompt_version: str
    version: int
    validated_by: str | None
    validated_at: datetime | None


class MinutesRevision(BaseModel):
    meeting_id: str
    version: int
    saved_by: str
    saved_at: datetime
    status: Literal["draft", "validated"]
    content: Minutes
    template: str
    model_name: str
    prompt_version: str


def _required(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 200:
        raise ValueError("Actor and provenance fields must contain 1 to 200 characters")
    return value


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _view(row: MinutesRow) -> StoredMinutes:
    return StoredMinutes(
        meeting_id=row.meeting_id,
        status=row.status,
        content=Minutes.model_validate(row.content),
        template=row.template,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        version=row.version,
        validated_by=row.validated_by,
        validated_at=_utc(row.validated_at) if row.validated_at else None,
    )


class MinutesService:
    """Caller owns the outer transaction; each mutation also has an atomic savepoint.

    Supply a trusted actor id, such as an authenticated user id or generation worker id.
    Never retry a stale version without first showing the latest content to the caller.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _row(self, meeting_id: str) -> MinutesRow:
        row = await self.session.scalar(
            select(MinutesRow)
            .where(MinutesRow.meeting_id == meeting_id)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise MinutesNotFound("No minutes for this meeting")
        return row

    async def get(self, meeting_id: str) -> StoredMinutes:
        return _view(await self._row(meeting_id))

    async def revisions(self, meeting_id: str) -> list[MinutesRevision]:
        await self._row(meeting_id)
        rows = await self.session.scalars(
            select(MinutesRevisionRow)
            .where(MinutesRevisionRow.meeting_id == meeting_id)
            .order_by(MinutesRevisionRow.version)
        )
        return [
            MinutesRevision(
                meeting_id=r.meeting_id,
                version=r.version,
                saved_by=r.saved_by,
                saved_at=_utc(r.saved_at),
                status=r.status,
                content=Minutes.model_validate(r.content),
                template=r.template,
                model_name=r.model_name,
                prompt_version=r.prompt_version,
            )
            for r in rows
        ]

    async def _transition_meeting(self, meeting_id: str, target: MeetingStatus) -> None:
        meeting = await self.session.scalar(
            select(MeetingRow)
            .where(MeetingRow.id == meeting_id)
            .execution_options(populate_existing=True)
        )
        if meeting is None:
            raise MinutesNotFound("Unknown meeting")
        source = MeetingStatus(meeting.status)
        check_transition(source, target)
        change = Transition(from_status=source, to_status=target)
        changed = await self.session.execute(
            update(MeetingRow)
            .where(MeetingRow.id == meeting_id, MeetingRow.version == meeting.version)
            .values(
                status=target,
                version=meeting.version + 1,
                updated_at=change.at,
                transitions=[*meeting.transitions, change.model_dump(mode="json")],
            )
            .execution_options(synchronize_session=False)
            .returning(MeetingRow.id)
        )
        if changed.scalar_one_or_none() is None:
            raise MinutesConflict("Meeting changed; reload before saving minutes")

    async def _revision(self, row: MinutesRow, actor: str) -> None:
        self.session.add(
            MinutesRevisionRow(
                meeting_id=row.meeting_id,
                version=row.version,
                saved_by=actor,
                saved_at=datetime.now(UTC),
                status=row.status,
                content=row.content,
                template=row.template,
                model_name=row.model_name,
                prompt_version=row.prompt_version,
            )
        )
        await self.session.flush()

    async def create_draft(
        self,
        meeting_id: str,
        content: Minutes,
        *,
        actor: str,
        template: str,
        model_name: str,
        prompt_version: str,
    ) -> StoredMinutes:
        actor, template, model_name, prompt_version = map(
            _required, (actor, template, model_name, prompt_version)
        )
        try:
            async with self.session.begin_nested():
                if await self.session.get(MinutesRow, meeting_id) is not None:
                    raise MinutesConflict("Minutes already exist for this meeting")
                await self._transition_meeting(meeting_id, MeetingStatus.DRAFT_READY)
                row = MinutesRow(
                    meeting_id=meeting_id,
                    status="draft",
                    content=content.model_dump(mode="json"),
                    template=template,
                    model_name=model_name,
                    prompt_version=prompt_version,
                    version=1,
                    validated_by=None,
                    validated_at=None,
                )
                self.session.add(row)
                await self.session.flush()
                await self._revision(row, actor)
                result = _view(row)
        except IntegrityError:
            raise MinutesConflict("Minutes were created concurrently") from None
        return result

    async def save_draft(
        self,
        meeting_id: str,
        content: Minutes,
        *,
        actor: str,
        expected_version: int,
    ) -> StoredMinutes:
        return await self._save(meeting_id, actor, expected_version, content=content)

    async def validate(
        self,
        meeting_id: str,
        *,
        actor: str,
        expected_version: int,
    ) -> StoredMinutes:
        return await self._save(meeting_id, actor, expected_version, validate=True)

    async def _save(
        self,
        meeting_id: str,
        actor: str,
        expected_version: int,
        *,
        content: Minutes | None = None,
        validate: bool = False,
    ) -> StoredMinutes:
        actor = _required(actor)
        async with self.session.begin_nested():
            row = await self._row(meeting_id)
            if row.status == "validated":
                raise ValidatedMinutesImmutable("Validated minutes cannot be modified")
            if row.version != expected_version:
                raise MinutesConflict("Stale minutes version; reload before saving")
            changed = await self.session.execute(
                update(MinutesRow)
                .where(
                    MinutesRow.meeting_id == meeting_id,
                    MinutesRow.status == "draft",
                    MinutesRow.version == expected_version,
                )
                .values(
                    content=content.model_dump(mode="json") if content is not None else row.content,
                    status="validated" if validate else "draft",
                    version=expected_version + 1,
                    validated_by=actor if validate else None,
                    validated_at=datetime.now(UTC) if validate else None,
                )
                .execution_options(synchronize_session=False)
                .returning(MinutesRow.meeting_id)
            )
            if changed.scalar_one_or_none() is None:
                raise MinutesConflict("Minutes changed concurrently; reload before saving")
            if validate:
                await self._transition_meeting(meeting_id, MeetingStatus.VALIDATED)
            row = await self._row(meeting_id)
            await self._revision(row, actor)
            return _view(row)
