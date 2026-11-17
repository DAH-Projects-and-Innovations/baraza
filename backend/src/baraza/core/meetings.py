"""Meeting lifecycle: the single definition of allowed user-facing transitions."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MeetingStatus(StrEnum):
    PENDING = "pending"
    CAPTURING = "capturing"
    PROCESSING = "processing"
    DRAFT_READY = "draft_ready"
    VALIDATED = "validated"
    ERROR = "error"


ALLOWED_TRANSITIONS: dict[MeetingStatus, frozenset[MeetingStatus]] = {
    MeetingStatus.PENDING: frozenset(
        {
            MeetingStatus.CAPTURING,
            MeetingStatus.PROCESSING,
            MeetingStatus.ERROR,
        }
    ),
    MeetingStatus.CAPTURING: frozenset({MeetingStatus.PROCESSING, MeetingStatus.ERROR}),
    MeetingStatus.PROCESSING: frozenset({MeetingStatus.DRAFT_READY, MeetingStatus.ERROR}),
    MeetingStatus.DRAFT_READY: frozenset({MeetingStatus.VALIDATED, MeetingStatus.ERROR}),
    MeetingStatus.VALIDATED: frozenset(),
    MeetingStatus.ERROR: frozenset({MeetingStatus.PENDING}),
}


class InvalidMeetingTransition(ValueError):
    pass


class Transition(BaseModel):
    from_status: MeetingStatus | None
    to_status: MeetingStatus
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def check_transition(source: MeetingStatus, target: MeetingStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[source]:
        raise InvalidMeetingTransition(f"Invalid meeting transition: {source} -> {target}")
