"""Persisted MVP record; separate from Thierry's meeting lifecycle in PR #197."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from baraza.adapters.base import CaptureStatus
from baraza.core.anti_invention import Correction
from baraza.core.minutes import Minutes
from baraza.core.transcript import Transcript


class MinutesRevision(BaseModel):
    """One saved version of the minutes: the assistant's draft, then each human save."""

    version: int
    saved_by: str
    saved_at: datetime
    status: Literal["draft", "validated"]
    content: Minutes


class Meeting(BaseModel):
    capture_id: str
    title: str
    meeting_url: str
    adapter: str
    template: str = "standard"
    participants_informed: Literal[True]
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: CaptureStatus = CaptureStatus.WAITING_ADMISSION
    transcript: Transcript | None = None
    minutes: Minutes | None = None
    # Traces des contrôles anti-invention, montrées aux relecteurs avec le brouillon.
    corrections: list[Correction] = Field(default_factory=list)
    prompt_version: str | None = None
    # Model that wrote the current draft (setting at generation time), shown with the draft.
    model_name: str | None = None
    # Review state of the minutes (see baraza.core.minutes_review).
    minutes_status: Literal["draft", "validated"] = "draft"
    minutes_version: int = 0
    validated_by: str | None = None
    validated_at: datetime | None = None
    revisions: list[MinutesRevision] = Field(default_factory=list)
    error: str | None = None
    simulated: bool = False
    # Who started the meeting (their email when signed in): the person notified about the draft.
    created_by: str | None = None
    stop_requested: bool = False
