"""Persisted MVP record; separate from Thierry's meeting lifecycle in PR #197."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from baraza.adapters.base import CaptureStatus
from baraza.core.anti_invention import Correction
from baraza.core.minutes import Minutes
from baraza.core.transcript import Transcript


class Meeting(BaseModel):
    capture_id: str
    title: str
    meeting_url: str
    adapter: str
    template: Literal["standard"] = "standard"
    participants_informed: Literal[True]
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: CaptureStatus = CaptureStatus.WAITING_ADMISSION
    transcript: Transcript | None = None
    minutes: Minutes | None = None
    # Traces des contrôles anti-invention, montrées aux relecteurs avec le brouillon.
    corrections: list[Correction] = Field(default_factory=list)
    prompt_version: str | None = None
    error: str | None = None
    simulated: bool = False
    stop_requested: bool = False
