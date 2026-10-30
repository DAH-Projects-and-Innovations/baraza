"""Durable meeting state and Vexa capture handles, sharing the segment database.

Like SqlSegmentStore, schema creation is temporary until the Alembic setup exists.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from baraza.core.meetings import MeetingStatus, Transition, check_transition
from baraza.storage.sql import Base
from baraza.vexa.client import BotResponse


class MeetingRow(Base):
    __tablename__ = "meetings"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=0)
    transitions: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaptureRow(Base):
    __tablename__ = "vexa_captures"
    meeting_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(200), unique=True)
    bot: Mapped[dict[str, object]] = mapped_column(JSON)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)


class StoredMeeting(BaseModel):
    id: str
    status: MeetingStatus
    transitions: list[Transition]


class StoredCapture(BaseModel):
    meeting_id: str
    bot: BotResponse


class ConcurrentMeetingTransition(RuntimeError):
    pass


class SqlCaptureStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._ready = False

    async def _ensure_schema(self) -> None:
        if not self._ready:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            self._ready = True

    async def create(self, meeting_id: str) -> None:
        await self._ensure_schema()
        initial = Transition(from_status=None, to_status=MeetingStatus.PENDING)
        async with self._sessions() as session, session.begin():
            session.add(
                MeetingRow(
                    id=meeting_id,
                    status=MeetingStatus.PENDING,
                    version=0,
                    transitions=[initial.model_dump(mode="json")],
                    updated_at=initial.at,
                )
            )

    async def get(self, meeting_id: str) -> StoredMeeting:
        await self._ensure_schema()
        async with self._sessions() as session:
            row = await session.get(MeetingRow, meeting_id)
            if row is None:
                raise ValueError("Unknown meeting id")
            return StoredMeeting(
                id=row.id,
                status=MeetingStatus(row.status),
                transitions=[Transition.model_validate(t) for t in row.transitions],
            )

    async def attach(self, meeting_id: str, bot: BotResponse) -> None:
        await self._ensure_schema()
        async with self._sessions() as session, session.begin():
            if await session.get(MeetingRow, meeting_id) is None:
                raise ValueError("Unknown meeting id")
            session.add(
                CaptureRow(
                    meeting_id=meeting_id,
                    bot_id=str(bot.id),
                    bot=bot.model_dump(mode="json"),
                    finished=False,
                )
            )

    async def captures(self, *, active_only: bool = True) -> list[StoredCapture]:
        await self._ensure_schema()
        statement = select(CaptureRow)
        if active_only:
            statement = statement.where(CaptureRow.finished.is_(False))
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
            return [
                StoredCapture(meeting_id=r.meeting_id, bot=BotResponse.model_validate(r.bot))
                for r in rows
            ]

    async def transition(
        self,
        meeting_id: str,
        target: MeetingStatus,
        *,
        finish_capture: bool = False,
        if_changed: bool = False,
    ) -> None:
        await self._ensure_schema()
        async with self._sessions() as session, session.begin():
            row = await session.get(MeetingRow, meeting_id)
            if row is None:
                raise ValueError("Unknown meeting id")
            source = MeetingStatus(row.status)
            if source != target or not if_changed:
                check_transition(source, target)
                change = Transition(from_status=source, to_status=target, at=datetime.now(UTC))
                statement = (
                    update(MeetingRow)
                    .where(
                        MeetingRow.id == meeting_id,
                        MeetingRow.version == row.version,
                    )
                    .values(
                        status=target,
                        version=row.version + 1,
                        updated_at=change.at,
                        transitions=[*row.transitions, change.model_dump(mode="json")],
                    )
                    .returning(MeetingRow.id)
                )
                if (await session.execute(statement)).scalar_one_or_none() is None:
                    raise ConcurrentMeetingTransition("Meeting changed; retry after reloading")
            if finish_capture:
                await session.execute(
                    update(CaptureRow)
                    .where(
                        CaptureRow.meeting_id == meeting_id,
                    )
                    .values(finished=True)
                )
