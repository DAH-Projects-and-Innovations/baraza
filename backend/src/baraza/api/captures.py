"""Frontend capture contract, independent of the concrete capture provider."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, field_validator

from baraza.adapters.base import CaptureAdapter, CaptureStatus
from baraza.api.dependencies import get_capture_adapter
from baraza.api.meetings import MeetingStoreDep, QueueDep, require_meeting, submit_transcript
from baraza.api.segments import StoreDep
from baraza.core.meeting_record import Meeting

router = APIRouter(prefix="/captures", tags=["captures"])
AdapterDep = Annotated[CaptureAdapter | None, Depends(get_capture_adapter)]


def require_adapter(adapter: CaptureAdapter | None) -> CaptureAdapter:
    if adapter is None:
        raise HTTPException(
            status_code=503,
            detail="Live capture is unavailable. Configure Vexa or use the labelled demo.",
        )
    return adapter


class StartCaptureRequest(BaseModel):
    meeting_url: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            pattern=r"^https://meet\.google\.com/(?:meet/)?[a-z]{3}-[a-z]{4}-[a-z]{3}(\?[^\s#]*)?$",
        ),
    ]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    template: Literal["standard"] = "standard"
    participants_informed: Literal[True]

    @field_validator("meeting_url")
    @classmethod
    def canonical_meet_url(cls, value: str) -> str:
        return value.replace("https://meet.google.com/meet/", "https://meet.google.com/")


class CaptureResponse(BaseModel):
    capture_id: str
    meeting_id: str
    title: str
    status: CaptureStatus
    simulated: bool
    stop_requested: bool = False
    error: str | None = None
    can_retry: bool = False
    phase: str = Field(description="Human-readable processing stage; no invented percentage.")


def capture_response(meeting: Meeting) -> CaptureResponse:
    return CaptureResponse(
        capture_id=meeting.capture_id,
        meeting_id=meeting.capture_id,
        title=meeting.title,
        status=meeting.status,
        simulated=meeting.simulated,
        stop_requested=meeting.stop_requested,
        error=meeting.error,
        can_retry=meeting.status == CaptureStatus.FAILED and meeting.transcript is not None,
        phase={
            CaptureStatus.WAITING_ADMISSION: "Waiting for admission",
            CaptureStatus.CAPTURING: "Receiving transcript",
            CaptureStatus.PROCESSING: "Generating draft minutes",
            CaptureStatus.DONE: "Draft ready for review",
            CaptureStatus.FAILED: "Action required",
        }[meeting.status],
    )


@router.post("", status_code=201)
async def start_capture(
    payload: StartCaptureRequest,
    store: MeetingStoreDep,
    adapter: AdapterDep,
) -> CaptureResponse:
    adapter = require_adapter(adapter)
    try:
        capture_id = await adapter.start(payload.meeting_url)
    except Exception as error:
        raise HTTPException(
            status_code=502, detail="Capture service could not start the bot."
        ) from error
    meeting = Meeting(
        capture_id=capture_id,
        title=payload.title,
        meeting_url=payload.meeting_url,
        adapter=adapter.name,
        participants_informed=True,
        simulated=adapter.name == "fake",
    )
    try:
        await store.save(meeting)
    except Exception:
        await adapter.stop(capture_id)
        raise
    return capture_response(meeting)


@router.get("/{capture_id}")
async def get_capture(
    capture_id: str,
    store: MeetingStoreDep,
    segments: StoreDep,
    queue: QueueDep,
    adapter: AdapterDep,
) -> CaptureResponse:
    meeting = await require_meeting(store, capture_id)
    if meeting.status in (CaptureStatus.WAITING_ADMISSION, CaptureStatus.CAPTURING):
        previous = meeting.model_dump_json()
        adapter = require_adapter(adapter)
        try:
            status = await adapter.status(capture_id)
            if status in (CaptureStatus.DONE, CaptureStatus.PROCESSING):
                transcript = await adapter.fetch_transcript(capture_id)
                meeting = await submit_transcript(
                    meeting, transcript.model_dump(), store, segments, queue
                )
            else:
                meeting.status = status
                if status == CaptureStatus.FAILED:
                    meeting.error = (
                        "The bot could not capture the meeting. Check admission and retry."
                    )
                if not await store.replace_if_unchanged(meeting, previous):
                    meeting = await require_meeting(store, capture_id)
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=502, detail="Cannot read the capture service status."
            ) from error
    return capture_response(meeting)


@router.post("/{capture_id}/stop")
async def stop_capture(
    capture_id: str,
    store: MeetingStoreDep,
    segments: StoreDep,
    queue: QueueDep,
    adapter: AdapterDep,
) -> CaptureResponse:
    meeting = await require_meeting(store, capture_id)
    if meeting.status in (CaptureStatus.PROCESSING, CaptureStatus.DONE, CaptureStatus.FAILED):
        return capture_response(meeting)
    if meeting.stop_requested:
        return capture_response(meeting)
    adapter = require_adapter(adapter)
    previous = meeting.model_dump_json()
    try:
        await adapter.stop(capture_id)
        if adapter.name != "fake":
            # Vexa acknowledges the request before its final transcript is flushed.
            # Continue polling; only a completed provider status triggers ingestion.
            meeting.stop_requested = True
            if not await store.replace_if_unchanged(meeting, previous):
                meeting = await require_meeting(store, capture_id)
            return capture_response(meeting)
        transcript = await adapter.fetch_transcript(capture_id)
    except Exception as error:
        raise HTTPException(
            status_code=502, detail="Could not stop capture or retrieve its transcript. Try again."
        ) from error
    try:
        meeting = await submit_transcript(meeting, transcript.model_dump(), store, segments, queue)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        meeting = await require_meeting(store, capture_id)
    return capture_response(meeting)
