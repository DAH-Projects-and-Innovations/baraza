"""Endpoints receiving and returning a meeting's transcript segments."""

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.ext.asyncio import create_async_engine

from baraza.config import get_settings
from baraza.core.ingestion import IngestResult, SegmentStore, ingest_segments
from baraza.core.segments import TranscriptSegment
from baraza.storage.sql import SqlSegmentStore

MAX_BATCH = 500

router = APIRouter(prefix="/meetings/{meeting_id}/segments", tags=["segments"])


@lru_cache
def get_segment_store() -> SegmentStore:
    return SqlSegmentStore(create_async_engine(get_settings().database_url))


StoreDep = Annotated[SegmentStore, Depends(get_segment_store)]


@router.post("")
async def post_segments(
    meeting_id: str,
    segments: Annotated[list[dict[str, Any]], Field(max_length=MAX_BATCH)],
    store: StoreDep,
) -> IngestResult:
    """Ingest a batch of segments. Invalid ones are reported by index; valid ones are stored."""
    if not segments:
        raise HTTPException(status_code=422, detail="Empty batch")
    return await ingest_segments(store, meeting_id, segments)


@router.get("")
async def get_segments(meeting_id: str, store: StoreDep) -> list[TranscriptSegment]:
    return await store.list(meeting_id)
