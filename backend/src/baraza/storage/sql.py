"""SQLAlchemy storage for transcript segments (PostgreSQL in production)."""

from sqlalchemy import Boolean, Float, String, Text, delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from baraza.core.meeting_record import Meeting
from baraza.core.segments import TranscriptSegment


class Base(DeclarativeBase):
    pass


class SegmentRow(Base):
    __tablename__ = "transcript_segments"

    meeting_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    segment_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    speaker: Mapped[str] = mapped_column(String(200))
    speaker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start: Mapped[float] = mapped_column(Float, index=True)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)


class SqlSegmentStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._ready = False

    async def replace(self, meeting_id: str, segments: list[TranscriptSegment]) -> None:
        await self._ensure_schema()
        async with self._sessions() as session, session.begin():
            await session.execute(delete(SegmentRow).where(SegmentRow.meeting_id == meeting_id))
            session.add_all(SegmentRow(**segment.model_dump()) for segment in segments)

    async def _ensure_schema(self) -> None:
        # TODO: replace with an Alembic migration once the migrations setup exists.
        if not self._ready:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            self._ready = True

    async def upsert(self, segments: list[TranscriptSegment]) -> None:
        await self._ensure_schema()
        async with self._sessions() as session, session.begin():
            for segment in segments:
                current = await session.get(SegmentRow, (segment.meeting_id, segment.segment_id))
                if current is None or not current.is_final or segment.is_final:
                    await session.merge(SegmentRow(**segment.model_dump()))

    async def list(self, meeting_id: str) -> list[TranscriptSegment]:
        await self._ensure_schema()
        statement = (
            select(SegmentRow)
            .where(SegmentRow.meeting_id == meeting_id)
            .order_by(SegmentRow.start, SegmentRow.end, SegmentRow.segment_id)
        )
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
        return [
            TranscriptSegment(
                meeting_id=r.meeting_id,
                segment_id=r.segment_id,
                speaker=r.speaker,
                speaker_id=r.speaker_id,
                start=r.start,
                end=r.end,
                text=r.text,
                language=r.language,
                is_final=r.is_final,
            )
            for r in rows
        ]


class MeetingRecordRow(Base):
    __tablename__ = "meeting_records"

    capture_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class SqlMeetingStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def _ensure_schema(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def get(self, capture_id: str) -> Meeting | None:
        await self._ensure_schema()
        async with self._sessions() as session:
            row = await session.get(MeetingRecordRow, capture_id)
            return Meeting.model_validate_json(row.payload) if row else None

    async def save(self, meeting: Meeting) -> None:
        await self._ensure_schema()
        async with self._sessions() as session, session.begin():
            await session.merge(
                MeetingRecordRow(capture_id=meeting.capture_id, payload=meeting.model_dump_json())
            )

    async def replace_if_unchanged(self, meeting: Meeting, previous: str) -> bool:
        """Claim a transition without overwriting a concurrent stop or worker result."""
        await self._ensure_schema()
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(MeetingRecordRow)
                .where(
                    MeetingRecordRow.capture_id == meeting.capture_id,
                    MeetingRecordRow.payload == previous,
                )
                .values(payload=meeting.model_dump_json())
            )
            return result.rowcount == 1
