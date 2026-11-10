"""SQLAlchemy storage for transcript segments (PostgreSQL in production)."""

from sqlalchemy import Boolean, Float, String, Text, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from baraza.core.segments import TranscriptSegment
from baraza.db.base import Base


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

    async def upsert(self, segments: list[TranscriptSegment]) -> None:
        async with self._sessions() as session, session.begin():
            for segment in segments:
                await session.merge(SegmentRow(**segment.model_dump()))

    async def list(self, meeting_id: str) -> list[TranscriptSegment]:
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
