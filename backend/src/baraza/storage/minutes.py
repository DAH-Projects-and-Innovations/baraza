"""Minutes and their append-only service-managed revision history."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from baraza.db.base import Base

CONTENT_TYPE = JSON().with_variant(JSONB(), "postgresql")


class MinutesRow(Base):
    __tablename__ = "minutes"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'validated')", name="status"),
        CheckConstraint("version >= 1", name="positive_version"),
        CheckConstraint(
            "(status = 'draft' AND validated_by IS NULL AND validated_at IS NULL) OR "
            "(status = 'validated' AND validated_by IS NOT NULL AND validated_at IS NOT NULL)",
            name="validation_metadata",
        ),
    )
    meeting_id: Mapped[str] = mapped_column(
        String(200), ForeignKey("meetings.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, object]] = mapped_column(CONTENT_TYPE)
    template: Mapped[str] = mapped_column(String(200))
    model_name: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer)
    validated_by: Mapped[str | None] = mapped_column(String(200))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MinutesRevisionRow(Base):
    __tablename__ = "minutes_revisions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'validated')", name="status"),
        CheckConstraint("version >= 1", name="positive_version"),
    )
    meeting_id: Mapped[str] = mapped_column(
        String(200), ForeignKey("minutes.meeting_id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    saved_by: Mapped[str] = mapped_column(String(200))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, object]] = mapped_column(CONTENT_TYPE)
    template: Mapped[str] = mapped_column(String(200))
    model_name: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(200))
