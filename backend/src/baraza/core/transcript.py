"""Common transcript format.

This is the only contract between capture adapters and the core. Any
breaking change must bump ``SCHEMA_VERSION``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION: Literal["1.0"] = "1.0"


class Participant(BaseModel):
    name: str
    email: str | None = None


class Segment(BaseModel):
    speaker: str = Field(description='Speaker name, or "Speaker 1" when unknown.')
    start: float = Field(ge=0, description="Start time, in seconds from the meeting start.")
    end: float = Field(ge=0, description="End time, in seconds from the meeting start.")
    text: str


class MeetingMetadata(BaseModel):
    title: str
    started_at: datetime
    duration_seconds: float | None = None
    platform: Literal["google_meet", "teams", "zoom", "file", "other"]
    organizer: str | None = None


class Transcript(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    meeting: MeetingMetadata
    participants: list[Participant] = []
    segments: list[Segment]
    language: str = Field(description='Detected language, ISO 639-1 code (e.g. "fr", "en").')
    source_adapter: str = Field(description="Identifier of the adapter that produced it.")
