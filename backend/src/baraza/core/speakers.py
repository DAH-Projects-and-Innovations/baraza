"""Naming the people a transcript could not name.

The capture often cannot tell who spoke and labels them "Speaker 3". A reviewer who knows
can give the label a name. The name is applied to every line of that speaker and, in a draft,
to the actions owned by that label, so the minutes and the transcript keep agreeing.
Validated minutes are locked, and so are their speakers.
"""

import re
from datetime import UTC, datetime

from baraza.core.meeting_record import Meeting, MinutesRevision

MAX_NAME_LENGTH = 200
UNNAMED = re.compile(r"^Speaker \d+$")


class InvalidSpeakerName(ValueError):
    """The new name is empty, too long or contains control characters."""


def clean_name(value: str) -> str:
    name = " ".join(value.split())
    if not name:
        raise InvalidSpeakerName("Enter a name")
    if len(name) > MAX_NAME_LENGTH:
        raise InvalidSpeakerName(f"Use at most {MAX_NAME_LENGTH} characters")
    if any(not ch.isprintable() for ch in name):
        raise InvalidSpeakerName("The name contains characters that cannot be shown")
    return name


def is_unnamed(speaker: str) -> bool:
    return UNNAMED.fullmatch(speaker) is not None


def rename_in_transcript(meeting: Meeting, old: str, new: str) -> int:
    """Rename a speaker on the meeting's transcript. Returns how many lines changed."""
    if meeting.transcript is None:
        return 0
    changed = 0
    for segment in meeting.transcript.segments:
        if segment.speaker == old:
            segment.speaker = new
            changed += 1
    return changed


def rename_owner(meeting: Meeting, old: str, new: str, *, actor: str) -> bool:
    """Carry the new name to the draft's action owners. A new version when something changed."""
    if meeting.minutes is None or not any(a.owner == old for a in meeting.minutes.actions):
        return False
    meeting.minutes = meeting.minutes.model_copy(
        update={
            "actions": [
                a.model_copy(update={"owner": new}) if a.owner == old else a
                for a in meeting.minutes.actions
            ]
        }
    )
    meeting.minutes_version += 1
    meeting.revisions.append(
        MinutesRevision(
            version=meeting.minutes_version,
            saved_by=actor,
            saved_at=datetime.now(UTC),
            status=meeting.minutes_status,
            content=meeting.minutes,
        )
    )
    return True
