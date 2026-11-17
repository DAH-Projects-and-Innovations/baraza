"""Endpoints receiving and returning a meeting's transcript segments."""

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from baraza.api.dependencies import get_engine, get_meeting_store
from baraza.core.ingestion import IngestResult, SegmentStore, ingest_segments
from baraza.core.segments import TranscriptSegment
from baraza.storage.sql import SqlMeetingStore, SqlSegmentStore

MAX_BATCH = 500

router = APIRouter(prefix="/meetings/{meeting_id}/segments", tags=["segments"])


@lru_cache
def get_segment_store() -> SegmentStore:
    return SqlSegmentStore(get_engine())


StoreDep = Annotated[SegmentStore, Depends(get_segment_store)]


@router.post("")
async def post_segments(
    meeting_id: str,
    segments: Annotated[list[dict[str, Any]], Field(max_length=MAX_BATCH)],
    store: StoreDep,
    meetings: Annotated[SqlMeetingStore, Depends(get_meeting_store)],
) -> IngestResult:
    """Ingest a batch of segments. Invalid ones are reported by index; valid ones are stored."""
    if not segments:
        raise HTTPException(status_code=422, detail="Empty batch")
    meeting = await meetings.get(meeting_id)
    if meeting is not None and meeting.transcript is not None:
        raise HTTPException(status_code=409, detail="The final transcript is already frozen.")
    return await ingest_segments(store, meeting_id, segments)


@router.get("")
async def get_segments(meeting_id: str, store: StoreDep) -> list[TranscriptSegment]:
    return await store.list(meeting_id)
