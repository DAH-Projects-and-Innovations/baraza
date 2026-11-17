"""Human review of generated minutes: edit a draft, validate it, keep every revision.

Rules (the product's trust model):
- The assistant's draft is version 1 and stays in the history.
- A draft can be edited by a person; every save creates a new version.
- Saving needs the version the person was looking at (optimistic locking), so two people
  cannot silently overwrite each other.
- Validated minutes are locked. Changing them later would be a new version of the meeting
  minutes, which is not part of this MVP.
- A source index must point to a real transcript segment, or the link would lie.
"""

from datetime import UTC, datetime

from pydantic import BaseModel

from baraza.core.meeting_record import Meeting, MinutesRevision
from baraza.core.minutes import Minutes


class MinutesNotAvailable(ValueError):
    """No generated minutes yet for this meeting."""


class StaleMinutes(ValueError):
    """The caller edited an older version than the current one."""


class MinutesLocked(ValueError):
    """Validated minutes cannot be modified."""


class InvalidSources(ValueError):
    """A decision, action, topic or open point cites a segment that does not exist."""


class MinutesCounts(BaseModel):
    decisions: int
    actions: int
    actions_without_owner: int
    actions_without_deadline: int
    open_points: int


def count_items(minutes: Minutes) -> MinutesCounts:
    return MinutesCounts(
        decisions=len(minutes.decisions),
        actions=len(minutes.actions),
        actions_without_owner=sum(1 for a in minutes.actions if not a.owner),
        actions_without_deadline=sum(1 for a in minutes.actions if not a.due_date),
        open_points=len(minutes.open_points),
    )


def _add_revision(meeting: Meeting, *, actor: str, content: Minutes) -> None:
    meeting.revisions.append(
        MinutesRevision(
            version=meeting.minutes_version,
            saved_by=actor,
            saved_at=datetime.now(UTC),
            status=meeting.minutes_status,
            content=content,
        )
    )


def record_generated(meeting: Meeting, minutes: Minutes, *, actor: str = "assistant") -> None:
    """Store a freshly generated draft as the next version of the meeting's minutes."""
    meeting.minutes = minutes
    meeting.minutes_status = "draft"
    meeting.minutes_version += 1
    meeting.validated_by = None
    meeting.validated_at = None
    _add_revision(meeting, actor=actor, content=minutes)


def _check_editable(meeting: Meeting, expected_version: int) -> Minutes:
    if meeting.minutes is None:
        raise MinutesNotAvailable("Minutes are not available yet")
    if meeting.minutes_status == "validated":
        raise MinutesLocked("Validated minutes cannot be modified")
    if meeting.minutes_version != expected_version:
        raise StaleMinutes("Another version was saved; reload before editing")
    return meeting.minutes


def check_sources(meeting: Meeting, minutes: Minutes) -> None:
    if meeting.transcript is None:
        return
    count = len(meeting.transcript.segments)
    sources = (
        [topic.source for topic in minutes.topics]
        + [decision.source for decision in minutes.decisions]
        + [action.source for action in minutes.actions]
        + [point.source for point in minutes.open_points]
    )
    if any(i < 0 or i >= count for s in sources for i in s.segment_indices):
        raise InvalidSources("An item cites a transcript segment that does not exist")


def save_edit(meeting: Meeting, content: Minutes, *, actor: str, expected_version: int) -> bool:
    """Apply a person's edit. Returns False when nothing changed (no new version)."""
    current = _check_editable(meeting, expected_version)
    check_sources(meeting, content)
    if content == current:
        return False
    meeting.minutes = content
    meeting.minutes_version += 1
    _add_revision(meeting, actor=actor, content=content)
    return True


def validate(meeting: Meeting, *, actor: str, expected_version: int) -> None:
    current = _check_editable(meeting, expected_version)
    meeting.minutes_status = "validated"
    meeting.minutes_version += 1
    meeting.validated_by = actor
    meeting.validated_at = datetime.now(UTC)
    _add_revision(meeting, actor=actor, content=current)
