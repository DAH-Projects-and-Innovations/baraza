"""Import all models before migration autogeneration."""

from baraza.storage.captures import CaptureRow, MeetingRow
from baraza.storage.minutes import MinutesRevisionRow, MinutesRow
from baraza.storage.sql import MeetingRecordRow, SegmentRow

__all__ = [
    "CaptureRow",
    "MeetingRecordRow",
    "MeetingRow",
    "MinutesRevisionRow",
    "MinutesRow",
    "SegmentRow",
]
