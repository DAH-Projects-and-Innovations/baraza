"""Validation and ingestion of transcript segments received during a meeting.

The store is a port: ``InMemorySegmentStore`` serves tests and local runs, and
``baraza.storage.sql.SqlSegmentStore`` persists to the database. Segment text is never logged.
"""

from collections.abc import Iterable
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from baraza.core.segments import TranscriptSegment


class SegmentStore(Protocol):
    async def upsert(self, segments: list[TranscriptSegment]) -> None:
        """Insert segments, replacing any with the same (meeting_id, segment_id)."""

    async def list(self, meeting_id: str) -> list[TranscriptSegment]:
        """Return a meeting's segments ordered by start, end, then segment id."""


class RejectedSegment(BaseModel):
    index: int
    errors: list[str]


class IngestResult(BaseModel):
    accepted: int
    rejected: list[RejectedSegment]


def _sort_key(segment: TranscriptSegment) -> tuple[float, float, str]:
    return (segment.start, segment.end, segment.segment_id)


class InMemorySegmentStore:
    def __init__(self) -> None:
        self._segments: dict[tuple[str, str], TranscriptSegment] = {}

    async def upsert(self, segments: list[TranscriptSegment]) -> None:
        for segment in segments:
            self._segments[(segment.meeting_id, segment.segment_id)] = segment

    async def list(self, meeting_id: str) -> list[TranscriptSegment]:
        found = (s for (m, _), s in self._segments.items() if m == meeting_id)
        return sorted(found, key=_sort_key)


def _error_messages(error: ValidationError) -> list[str]:
    # Only locations and messages: never echo the submitted values (they may be transcript text).
    return [
        f"{'.'.join(str(p) for p in e['loc']) or 'segment'}: {e['msg']}" for e in error.errors()
    ]


# Names used by capture sources, mapped to the common segment fields.
_ALIASES = {"start_time": "start", "end_time": "end"}


def normalize_raw_segment(raw: dict[str, Any]) -> dict[str, Any]:
    """Map source field names to the common format and label unnamed speakers.

    A segment with a ``speaker_id`` but no ``speaker`` is labelled "Speaker <id>": the identity
    is never guessed, only the source's own identifier is reused.
    """
    segment = dict(raw)
    for alias, field in _ALIASES.items():
        if alias in segment:
            segment.setdefault(field, segment.pop(alias))
    speaker = segment.get("speaker")
    speaker_id = segment.get("speaker_id")
    if (speaker is None or speaker == "") and speaker_id not in (None, ""):
        segment["speaker"] = f"Speaker {speaker_id}"
    return segment


async def ingest_segments(
    store: SegmentStore, meeting_id: str, raw_segments: Iterable[dict[str, Any]]
) -> IngestResult:
    """Validate raw segments and store the valid ones.

    ``meeting_id`` is imposed by the caller (e.g. the URL), so a payload cannot write into another
    meeting. Invalid segments are reported by index and do not prevent valid ones from being stored.
    """
    valid: list[TranscriptSegment] = []
    rejected: list[RejectedSegment] = []
    for index, raw in enumerate(raw_segments):
        try:
            valid.append(
                TranscriptSegment.model_validate(
                    {**normalize_raw_segment(raw), "meeting_id": meeting_id}
                )
            )
        except ValidationError as error:
            rejected.append(RejectedSegment(index=index, errors=_error_messages(error)))
    if valid:
        await store.upsert(valid)
    return IngestResult(accepted=len(valid), rejected=rejected)
