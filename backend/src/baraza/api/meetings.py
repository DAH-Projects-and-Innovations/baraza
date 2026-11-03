"""Final transcript ingestion and draft retrieval, shared by every adapter."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from baraza.adapters.base import CaptureStatus
from baraza.api.dependencies import GenerationQueue, get_generation_queue, get_meeting_store
from baraza.api.segments import StoreDep
from baraza.core.ingestion import SegmentStore
from baraza.core.meeting_record import Meeting
from baraza.core.minutes import Minutes
from baraza.core.segments import TranscriptSegment
from baraza.core.transcript import Transcript
from baraza.storage.sql import SqlMeetingStore

router = APIRouter(prefix="/meetings", tags=["meetings"])
MeetingStoreDep = Annotated[SqlMeetingStore, Depends(get_meeting_store)]
QueueDep = Annotated[GenerationQueue, Depends(get_generation_queue)]


async def require_meeting(store: SqlMeetingStore, meeting_id: str) -> Meeting:
    meeting = await store.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


async def submit_transcript(
    meeting: Meeting,
    raw: dict[str, Any],
    store: SqlMeetingStore,
    segments: SegmentStore,
    queue: GenerationQueue,
) -> Meeting:
    if meeting.status in (CaptureStatus.PROCESSING, CaptureStatus.DONE):
        raise HTTPException(status_code=409, detail="Transcript already submitted")
    previous = meeting.model_dump_json()
    try:
        transcript = Transcript.model_validate(raw)
    except ValidationError as error:
        # Never return Pydantic's input values: they may contain private transcript text.
        detail = "Invalid transcript: check schema_version, non-empty segments and timestamps."
        meeting.status = CaptureStatus.FAILED
        meeting.error = detail
        if not await store.replace_if_unchanged(meeting, previous):
            raise HTTPException(
                status_code=409, detail="Meeting state changed; reload its status."
            ) from error
        raise HTTPException(status_code=422, detail=detail) from error
    transcript.meeting.title = meeting.title
    transcript.segments.sort(key=lambda segment: (segment.start, segment.end))
    meeting.transcript = transcript
    meeting.status = CaptureStatus.PROCESSING
    meeting.error = None
    if not await store.replace_if_unchanged(meeting, previous):
        raise HTTPException(status_code=409, detail="Meeting state changed; reload its status.")
    await segments.replace(
        meeting.capture_id,
        [
            TranscriptSegment(
                **segment.model_dump(),
                meeting_id=meeting.capture_id,
                segment_id=f"final-{index:08d}",
                language=transcript.language,
            )
            for index, segment in enumerate(transcript.segments)
        ],
    )
    await store.save(meeting)
    try:
        await queue.enqueue(meeting.capture_id)
    except Exception as error:
        meeting.status = CaptureStatus.FAILED
        meeting.error = "Generation could not be queued. Retry when the task service is available."
        await store.save(meeting)
        raise HTTPException(status_code=503, detail=meeting.error) from error
    return meeting


@router.post("/{meeting_id}/transcript", status_code=202)
async def post_transcript(
    meeting_id: str,
    payload: dict[str, Any],
    store: MeetingStoreDep,
    segments: StoreDep,
    queue: QueueDep,
) -> Meeting:
    meeting = await require_meeting(store, meeting_id)
    return await submit_transcript(meeting, payload, store, segments, queue)


@router.get("/{meeting_id}/transcript")
async def get_transcript(meeting_id: str, store: MeetingStoreDep) -> Transcript:
    meeting = await require_meeting(store, meeting_id)
    if meeting.transcript is None:
        raise HTTPException(status_code=404, detail="Transcript is not available yet")
    return meeting.transcript


@router.get("/{meeting_id}/minutes")
async def get_minutes(meeting_id: str, store: MeetingStoreDep) -> Minutes:
    meeting = await require_meeting(store, meeting_id)
    if meeting.minutes is None:
        raise HTTPException(status_code=404, detail="Minutes are not available yet")
    return meeting.minutes


@router.post("/{meeting_id}/retry", status_code=202)
async def retry_generation(meeting_id: str, store: MeetingStoreDep, queue: QueueDep) -> Meeting:
    meeting = await require_meeting(store, meeting_id)
    if meeting.status != CaptureStatus.FAILED or meeting.transcript is None:
        raise HTTPException(status_code=409, detail="No failed generation to retry")
    previous = meeting.model_dump_json()
    meeting.status = CaptureStatus.PROCESSING
    meeting.error = None
    if not await store.replace_if_unchanged(meeting, previous):
        raise HTTPException(status_code=409, detail="Generation is already being retried.")
    try:
        await queue.enqueue(meeting_id)
    except Exception as error:
        meeting.status = CaptureStatus.FAILED
        meeting.error = (
            "Generation could not be queued. Try again when the task service is available."
        )
        await store.save(meeting)
        raise HTTPException(status_code=503, detail=meeting.error) from error
    return meeting
