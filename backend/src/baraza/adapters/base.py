"""Capture adapter contract.

A contributor should be able to write an adapter by reading only this file
and ``baraza.core.transcript``. See docs/adapters.md.
"""

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel

from baraza.core.transcript import Transcript


class CaptureStatus(StrEnum):
    WAITING_ADMISSION = "waiting_admission"
    CAPTURING = "capturing"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class AdapterCapabilities(BaseModel):
    platforms: list[str]
    realtime: bool
    provides_speaker_names: bool


class CaptureAdapter(ABC):
    """Interface shared by all adapters."""

    #: Stable identifier, copied into ``Transcript.source_adapter``.
    name: str

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities: ...

    @abstractmethod
    async def start(self, meeting_url: str) -> str:
        """Start capturing and return a capture identifier."""

    @abstractmethod
    async def stop(self, capture_id: str) -> None: ...

    @abstractmethod
    async def status(self, capture_id: str) -> CaptureStatus: ...

    @abstractmethod
    async def fetch_transcript(self, capture_id: str) -> Transcript:
        """Return the transcript in the common format once capture is done."""
