"""Common format for transcript segments received while a meeting is running.

``baraza.core.transcript.Transcript`` describes a whole, finished transcript. This module
describes the unit that streams in during capture: one ``TranscriptSegment``. Adapters convert
whatever their source exposes (Vexa, native Meet, file import...) into this format, and the
ingestion code stores it. Once capture is done, the stored segments are assembled into a
``Transcript`` for the minutes pipeline (see ``segments_to_transcript``).

Any breaking change must bump ``SEGMENT_SCHEMA_VERSION``.
"""

from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from baraza.core.transcript import MeetingMetadata, Participant, Segment, Transcript

SEGMENT_SCHEMA_VERSION: Literal["1.0"] = "1.0"

_Id = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TranscriptSegment(BaseModel):
    meeting_id: _Id = Field(description="Identifier of the meeting this segment belongs to.")
    segment_id: _Id = Field(
        description="Unique within the meeting. Re-sending the same id replaces the segment "
        "(a partial result is replaced by its final version)."
    )
    speaker: _Id = Field(description='Speaker name, or "Speaker 1" when unknown.')
    start: float = Field(ge=0, description="Start time, in seconds from the meeting start.")
    end: float = Field(ge=0, description="End time, in seconds from the meeting start.")
    text: _Text
    language: str | None = Field(
        default=None, description='ISO 639-1 code (e.g. "fr"), when known for this segment.'
    )
    is_final: bool = Field(
        default=True, description="False for a partial result that may still be revised."
    )

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


def segments_to_transcript(
    segments: Sequence[TranscriptSegment],
    meeting: MeetingMetadata,
    *,
    language: str,
    source_adapter: str,
    participants: list[Participant] | None = None,
) -> Transcript:
    """Assemble stored segments into the transcript consumed by the minutes pipeline.

    Only final segments are kept, ordered by start time (then end time, then id).
    """
    final = sorted(
        (s for s in segments if s.is_final), key=lambda s: (s.start, s.end, s.segment_id)
    )
    return Transcript(
        meeting=meeting,
        participants=participants or [],
        segments=[Segment(speaker=s.speaker, start=s.start, end=s.end, text=s.text) for s in final],
        language=language,
        source_adapter=source_adapter,
    )
