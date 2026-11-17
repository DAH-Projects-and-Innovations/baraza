"""Common transcript format.

This is the only contract between capture adapters and the core. Any
breaking change must bump ``SCHEMA_VERSION``.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

SCHEMA_VERSION: Literal["1.0"] = "1.0"


class Participant(BaseModel):
    name: NonEmpty
    email: str | None = None


class Segment(BaseModel):
    speaker: NonEmpty = Field(description='Speaker name, or "Speaker 1" when unknown.')
    start: float = Field(ge=0, allow_inf_nan=False, description="Start time in seconds.")
    end: float = Field(ge=0, allow_inf_nan=False, description="End time in seconds.")
    text: NonEmpty

    @model_validator(mode="after")
    def check_times(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class MeetingMetadata(BaseModel):
    title: NonEmpty
    started_at: datetime
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    platform: Literal["google_meet", "teams", "zoom", "file", "other"]
    organizer: str | None = None


class Transcript(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    meeting: MeetingMetadata
    participants: list[Participant] = []
    segments: list[Segment] = Field(min_length=1)
    language: str = Field(
        pattern=r"^(?:[a-z]{2}|und)$", description="ISO 639-1 code, or und when unknown."
    )
    source_adapter: NonEmpty = Field(description="Identifier of the adapter that produced it.")

    @model_validator(mode="after")
    def check_duration(self) -> Self:
        duration = self.meeting.duration_seconds
        if duration is not None and any(s.end > duration for s in self.segments):
            raise ValueError("segment end exceeds meeting duration")
        return self
