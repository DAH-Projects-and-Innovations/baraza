"""SQLAlchemy storage for transcript segments (PostgreSQL in production)."""

from sqlalchemy import Boolean, Float, String, Text, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from baraza.core.segments import TranscriptSegment


class Base(DeclarativeBase):
    pass


class SegmentRow(Base):
    __tablename__ = "transcript_segments"

    meeting_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    segment_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    speaker: Mapped[str] = mapped_column(String(200))
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
                start=r.start,
                end=r.end,
                text=r.text,
                language=r.language,
                is_final=r.is_final,
            )
            for r in rows
        ]
