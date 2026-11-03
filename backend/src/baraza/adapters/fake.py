"""Explicitly simulated capture for the internal demo. Never connects to Meet."""

from datetime import UTC, datetime
from uuid import uuid4

from baraza.adapters.base import AdapterCapabilities, CaptureAdapter, CaptureStatus
from baraza.core.transcript import MeetingMetadata, Segment, Transcript


class FakeCaptureAdapter(CaptureAdapter):
    name = "fake"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            platforms=["google_meet"], realtime=False, provides_speaker_names=True
        )

    async def start(self, meeting_url: str) -> str:
        return f"demo-{uuid4()}"

    async def stop(self, capture_id: str) -> None:
        return None

    async def status(self, capture_id: str) -> CaptureStatus:
        return CaptureStatus.CAPTURING

    async def fetch_transcript(self, capture_id: str) -> Transcript:
        return Transcript(
            meeting=MeetingMetadata(
                title="Fictional demo meeting", started_at=datetime.now(UTC), platform="file"
            ),
            language="en",
            source_adapter=self.name,
            segments=[
                Segment(
                    speaker="Awa Example",
                    start=0,
                    end=8,
                    text="We agree to move the launch to March.",
                ),
                Segment(
                    speaker="Koffi Test",
                    start=8,
                    end=15,
                    text="I will prepare the launch plan by Friday.",
                ),
                Segment(
                    speaker="Speaker 3",
                    start=15,
                    end=20,
                    text="The budget remains an open question.",
                ),
            ],
        )
