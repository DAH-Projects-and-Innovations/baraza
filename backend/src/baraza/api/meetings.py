"""Final transcript ingestion and draft retrieval, shared by every adapter."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, ValidationError

from baraza.adapters.base import CaptureStatus
from baraza.api.dependencies import (
    GenerationQueue,
    get_actor,
    get_generation_queue,
    get_meeting_store,
)
from baraza.api.segments import StoreDep
from baraza.core.anti_invention import Correction
from baraza.core.ingestion import SegmentStore
from baraza.core.meeting_record import Meeting
from baraza.core.minutes import Minutes
from baraza.core.minutes_review import (
    InvalidSources,
    MinutesCounts,
    MinutesLocked,
    MinutesNotAvailable,
    StaleMinutes,
    count_items,
    save_edit,
    validate,
)
from baraza.core.segments import TranscriptSegment
from baraza.core.speakers import InvalidSpeakerName, clean_name, rename_in_transcript, rename_owner
from baraza.core.transcript import Transcript
from baraza.storage.sql import SqlMeetingStore

router = APIRouter(prefix="/meetings", tags=["meetings"])
MeetingStoreDep = Annotated[SqlMeetingStore, Depends(get_meeting_store)]
QueueDep = Annotated[GenerationQueue, Depends(get_generation_queue)]
ActorDep = Annotated[str, Depends(get_actor)]


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


def etag(version: int) -> str:
    return f'"{version}"'


def expected_version(if_match: str | None) -> int:
    """The version the person was looking at, sent as ``If-Match``."""
    if if_match is None:
        raise HTTPException(status_code=428, detail="Send the version you are editing: If-Match")
    try:
        return int(if_match.strip().removeprefix("W/").strip('"'))
    except ValueError:
        raise HTTPException(status_code=400, detail="If-Match must be a version number") from None


class MinutesState(BaseModel):
    meeting_id: str
    status: Literal["draft", "validated"]
    version: int
    validated_by: str | None
    validated_at: datetime | None
    prompt_version: str | None
    corrections: list[Correction]
    counts: MinutesCounts


class RevisionSummary(BaseModel):
    version: int
    saved_by: str
    saved_at: datetime
    status: Literal["draft", "validated"]


def minutes_state(meeting: Meeting) -> MinutesState:
    if meeting.minutes is None:
        raise HTTPException(status_code=404, detail="Minutes are not available yet")
    return MinutesState(
        meeting_id=meeting.capture_id,
        status=meeting.minutes_status,
        version=meeting.minutes_version,
        validated_by=meeting.validated_by,
        validated_at=meeting.validated_at,
        prompt_version=meeting.prompt_version,
        corrections=meeting.corrections,
        counts=count_items(meeting.minutes),
    )


class MeetingSummary(BaseModel):
    meeting_id: str
    title: str
    status: CaptureStatus
    started_at: datetime
    simulated: bool
    duration_seconds: float | None
    participants: int
    minutes_status: Literal["draft", "validated"] | None
    minutes_version: int
    needs_review: bool
    counts: MinutesCounts | None


class MeetingList(BaseModel):
    items: list[MeetingSummary]
    total: int
    limit: int
    offset: int


def summarize(meeting: Meeting) -> MeetingSummary:
    transcript = meeting.transcript
    duration = max((s.end for s in transcript.segments), default=None) if transcript else None
    return MeetingSummary(
        meeting_id=meeting.capture_id,
        title=meeting.title,
        status=meeting.status,
        started_at=meeting.started_at,
        simulated=meeting.simulated,
        duration_seconds=duration,
        participants=len({s.speaker for s in transcript.segments}) if transcript else 0,
        minutes_status=meeting.minutes_status if meeting.minutes else None,
        minutes_version=meeting.minutes_version,
        needs_review=meeting.minutes is not None and meeting.minutes_status == "draft",
        counts=count_items(meeting.minutes) if meeting.minutes else None,
    )


@router.get("")
async def list_meetings(
    store: MeetingStoreDep,
    status: CaptureStatus | None = None,
    needs_review: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MeetingList:
    """Meeting history, most recent first. ``needs_review`` lists drafts waiting for a person."""
    meetings = sorted(await store.list_all(), key=lambda m: m.started_at, reverse=True)
    items = [summarize(m) for m in meetings]
    if status is not None:
        items = [i for i in items if i.status == status]
    if needs_review is not None:
        items = [i for i in items if i.needs_review == needs_review]
    page = items[offset : offset + limit]
    return MeetingList(items=page, total=len(items), limit=limit, offset=offset)


@router.get("/{meeting_id}/minutes")
async def get_minutes(meeting_id: str, store: MeetingStoreDep, response: Response) -> Minutes:
    meeting = await require_meeting(store, meeting_id)
    if meeting.minutes is None:
        raise HTTPException(status_code=404, detail="Minutes are not available yet")
    response.headers["ETag"] = etag(meeting.minutes_version)
    response.headers["X-Minutes-Status"] = meeting.minutes_status
    return meeting.minutes


@router.get("/{meeting_id}/minutes/meta")
async def get_minutes_state(meeting_id: str, store: MeetingStoreDep) -> MinutesState:
    return minutes_state(await require_meeting(store, meeting_id))


@router.get("/{meeting_id}/minutes/revisions")
async def list_revisions(meeting_id: str, store: MeetingStoreDep) -> list[RevisionSummary]:
    meeting = await require_meeting(store, meeting_id)
    return [
        RevisionSummary(
            version=r.version, saved_by=r.saved_by, saved_at=r.saved_at, status=r.status
        )
        for r in meeting.revisions
    ]


@router.get("/{meeting_id}/minutes/revisions/{version}")
async def get_revision(meeting_id: str, version: int, store: MeetingStoreDep) -> Minutes:
    meeting = await require_meeting(store, meeting_id)
    for revision in meeting.revisions:
        if revision.version == version:
            return revision.content
    raise HTTPException(status_code=404, detail="Unknown revision")


async def apply_review(
    meeting_id: str,
    store: SqlMeetingStore,
    response: Response,
    change: Callable[[Meeting], bool | None],
) -> MinutesState:
    meeting = await require_meeting(store, meeting_id)
    previous = meeting.model_dump_json()
    try:
        changed = change(meeting)
    except MinutesNotAvailable as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except MinutesLocked as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except StaleMinutes as error:
        raise HTTPException(
            status_code=412, detail=str(error), headers={"ETag": etag(meeting.minutes_version)}
        ) from error
    except InvalidSources as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if changed is not False and not await store.replace_if_unchanged(meeting, previous):
        raise HTTPException(status_code=409, detail="The meeting changed; reload and try again")
    response.headers["ETag"] = etag(meeting.minutes_version)
    return minutes_state(meeting)


@router.put("/{meeting_id}/minutes")
async def save_minutes(
    meeting_id: str,
    content: Minutes,
    store: MeetingStoreDep,
    response: Response,
    actor: ActorDep,
    if_match: Annotated[str | None, Header()] = None,
) -> MinutesState:
    """Save a person's edit of the draft. Send the version you started from in ``If-Match``."""
    version = expected_version(if_match)
    return await apply_review(
        meeting_id,
        store,
        response,
        lambda m: save_edit(m, content, actor=actor, expected_version=version),
    )


@router.post("/{meeting_id}/minutes/validate")
async def validate_minutes(
    meeting_id: str,
    store: MeetingStoreDep,
    response: Response,
    actor: ActorDep,
    if_match: Annotated[str | None, Header()] = None,
) -> MinutesState:
    """Mark the draft as validated. The minutes are locked afterwards."""
    version = expected_version(if_match)

    def mark_validated(meeting: Meeting) -> None:
        validate(meeting, actor=actor, expected_version=version)

    return await apply_review(meeting_id, store, response, mark_validated)


class RenameSpeaker(BaseModel):
    from_name: str = Field(min_length=1, max_length=200)
    to_name: str = Field(max_length=1024)


class RenameResult(BaseModel):
    renamed_segments: int
    # Set when the draft's action owners were updated too (a new version of the minutes).
    minutes_version: int | None


@router.post("/{meeting_id}/speakers/rename")
async def rename_speaker(
    meeting_id: str,
    payload: RenameSpeaker,
    store: MeetingStoreDep,
    segments: StoreDep,
    actor: ActorDep,
) -> RenameResult:
    """Give a name to a speaker the capture could not name ("Speaker 3").

    The name is applied to every line of that speaker, and to the draft's action owners.
    Validated minutes are locked: so are their speakers.
    """
    meeting = await require_meeting(store, meeting_id)
    if meeting.minutes is not None and meeting.minutes_status == "validated":
        raise HTTPException(status_code=409, detail="Validated minutes are locked")
    try:
        new = clean_name(payload.to_name)
    except InvalidSpeakerName as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    old = payload.from_name
    if new == old:
        raise HTTPException(status_code=422, detail="This is already the name")
    # The segment store is updated first and the change is idempotent: a retry finishes the job.
    stored = [s for s in await segments.list(meeting_id) if s.speaker == old]
    previous = meeting.model_dump_json()
    in_transcript = rename_in_transcript(meeting, old, new)
    if not stored and not in_transcript:
        raise HTTPException(status_code=404, detail="Unknown speaker")
    if stored:
        await segments.upsert([s.model_copy(update={"speaker": new}) for s in stored])
    owners_changed = rename_owner(meeting, old, new, actor=actor)
    if (in_transcript or owners_changed) and not await store.replace_if_unchanged(
        meeting, previous
    ):
        raise HTTPException(status_code=409, detail="The meeting changed; reload and try again")
    return RenameResult(
        renamed_segments=max(len(stored), in_transcript),
        minutes_version=meeting.minutes_version if owners_changed else None,
    )


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
