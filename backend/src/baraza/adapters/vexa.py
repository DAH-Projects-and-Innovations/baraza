"""Google Meet adapter for official Vexa v0.12.26; no voice identity inference."""

import re
from urllib.parse import urlparse

from baraza.adapters.base import AdapterCapabilities, CaptureAdapter, CaptureStatus
from baraza.config import Settings
from baraza.core.segments import TranscriptSegment, segments_to_transcript
from baraza.core.transcript import MeetingMetadata, Transcript
from baraza.vexa.client import BotRequest, BotResponse, BotState, TranscriptResponse, VexaClient

STATUS_MAP: dict[BotState, CaptureStatus] = {
    "idle": CaptureStatus.WAITING_ADMISSION,
    "scheduled": CaptureStatus.WAITING_ADMISSION,
    "requested": CaptureStatus.WAITING_ADMISSION,
    "joining": CaptureStatus.WAITING_ADMISSION,
    "awaiting_admission": CaptureStatus.WAITING_ADMISSION,
    "needs_help": CaptureStatus.WAITING_ADMISSION,
    "active": CaptureStatus.CAPTURING,
    "stopping": CaptureStatus.CAPTURING,
    "completed": CaptureStatus.PROCESSING,
    "failed": CaptureStatus.FAILED,
}


def map_segments(payload: TranscriptResponse, meeting_id: str) -> list[TranscriptSegment]:
    # Avoid generated labels colliding with an explicit display name.
    used = {s.speaker.strip() for s in payload.segments if s.speaker and s.speaker.strip()}
    unknown: dict[str, str] = {}
    result = []
    for segment in sorted(payload.segments, key=lambda s: (s.start, s.end, s.segment_id)):
        speaker = (segment.speaker or "").strip()
        if not speaker:
            key = segment.speaker_id or "unattributed"
            if key not in unknown:
                index = 1
                while f"Speaker {index}" in used:
                    index += 1
                unknown[key] = f"Speaker {index}"
                used.add(unknown[key])
            speaker = unknown[key]
        result.append(
            TranscriptSegment(
                meeting_id=meeting_id,
                segment_id=segment.segment_id,
                speaker=speaker,
                speaker_id=segment.speaker_id,
                start=segment.start,
                end=segment.end,
                text=segment.text,
                language=segment.language,
                is_final=segment.completed,
            )
        )
    return result


class VexaAdapter(CaptureAdapter):
    name = "vexa"

    def __init__(self, client: VexaClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._known: dict[str, BotResponse] = {}

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            platforms=["google_meet"],
            realtime=True,
            provides_speaker_names=True,
        )

    def restore(self, bot: BotResponse) -> None:
        """Register a handle from trusted storage, never from an event body."""
        self._known[str(bot.id)] = bot

    def handle(self, capture_id: str) -> BotResponse:
        try:
            return self._known[capture_id]
        except KeyError:
            raise ValueError("Unknown Vexa capture id") from None

    def verify(self, capture_id: str, response: BotResponse) -> None:
        known = self.handle(capture_id)
        if (str(response.id), response.platform, response.native_meeting_id) != (
            capture_id,
            known.platform,
            known.native_meeting_id,
        ):
            raise ValueError("Vexa response does not match the registered capture")

    async def start(self, meeting_url: str) -> str:
        url = urlparse(meeting_url)
        if (
            url.scheme != "https"
            or url.netloc != "meet.google.com"
            or not re.fullmatch(r"/[a-z]{3}-[a-z]{4}-[a-z]{3}/?", url.path)
        ):
            raise ValueError("Expected a Google Meet HTTPS meeting URL")
        bot = await self.client.request_bot(
            BotRequest(
                platform="google_meet",
                native_meeting_id=url.path.strip("/"),
                meeting_url=meeting_url,
                bot_name=self.settings.vexa_bot_name,
            )
        )
        if bot.platform != "google_meet" or bot.native_meeting_id != url.path.strip("/"):
            raise ValueError("Vexa returned a different meeting")
        self.restore(bot)
        return str(bot.id)

    async def stop(self, capture_id: str) -> None:
        bot = self.handle(capture_id)
        stopped = await self.client.stop_bot(bot.platform, bot.native_meeting_id)
        if str(stopped.meeting_id) != capture_id:
            raise ValueError("Vexa stopped a different meeting")

    async def status(self, capture_id: str) -> CaptureStatus:
        self.handle(capture_id)
        bot = await self.client.get_bot(capture_id)
        self.verify(capture_id, bot)
        return STATUS_MAP[bot.status]

    async def transcript_payload(self, capture_id: str) -> TranscriptResponse:
        self.handle(capture_id)
        payload = await self.client.get_transcript(capture_id)
        self.verify(capture_id, payload)
        return payload

    async def fetch_transcript(self, capture_id: str) -> Transcript:
        payload = await self.transcript_payload(capture_id)
        if payload.status != "completed":
            raise ValueError("Vexa transcript is not complete")
        if payload.start_time is None:
            raise ValueError("Vexa transcript has no meeting start time")
        return segments_to_transcript(
            map_segments(payload, capture_id),
            MeetingMetadata(
                title="Google Meet",
                platform="google_meet",
                started_at=payload.start_time,
            ),
            language=next((s.language for s in payload.segments if s.language), "und"),
            source_adapter=self.name,
        )
