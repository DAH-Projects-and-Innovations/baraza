"""Poll trusted capture handles and feed the existing ingestion pipeline."""

from baraza.adapters.base import CaptureStatus
from baraza.adapters.vexa import VexaAdapter, map_segments
from baraza.core.ingestion import SegmentStore, ingest_segments
from baraza.core.meetings import MeetingStatus
from baraza.storage.captures import SqlCaptureStore, StoredCapture


class VexaCaptureService:
    def __init__(
        self,
        adapter: VexaAdapter,
        captures: SqlCaptureStore,
        segments: SegmentStore,
    ) -> None:
        self.adapter = adapter
        self.captures = captures
        self.segments = segments

    async def start(self, meeting_id: str, meeting_url: str) -> str:
        # Duplicate meeting ids are refused before any external spawn.
        await self.captures.create(meeting_id)
        try:
            capture_id = await self.adapter.start(meeting_url)
            await self.captures.attach(meeting_id, self.adapter.handle(capture_id))
        except Exception:
            await self.captures.transition(meeting_id, MeetingStatus.ERROR)
            raise
        return capture_id

    async def stop(self, meeting_id: str) -> None:
        capture = next(
            (c for c in await self.captures.captures() if c.meeting_id == meeting_id), None
        )
        if capture is None:
            raise ValueError("Unknown active capture")
        self.adapter.restore(capture.bot)
        await self.adapter.stop(str(capture.bot.id))
        # DELETE acknowledges stopping; wait for completed before retrieving the final transcript.

    async def poll(self, capture: StoredCapture) -> None:
        self.adapter.restore(capture.bot)
        capture_id = str(capture.bot.id)
        status = await self.adapter.status(capture_id)
        if status == CaptureStatus.FAILED:
            await self.captures.transition(
                capture.meeting_id,
                MeetingStatus.ERROR,
                finish_capture=True,
                if_changed=True,
            )
            return
        if status == CaptureStatus.WAITING_ADMISSION:
            return
        payload = await self.adapter.transcript_payload(capture_id)
        # State may advance between the two GETs; only completed means the final flush is ready.
        if payload.status == "failed":
            await self.captures.transition(
                capture.meeting_id,
                MeetingStatus.ERROR,
                finish_capture=True,
                if_changed=True,
            )
            return
        segments = map_segments(payload, capture.meeting_id)
        result = await ingest_segments(
            self.segments,
            capture.meeting_id,
            [s.model_dump() for s in segments],
        )
        if result.rejected:
            raise ValueError("Vexa returned invalid transcript segments")
        completed = payload.status == "completed"
        await self.captures.transition(
            capture.meeting_id,
            MeetingStatus.PROCESSING if completed else MeetingStatus.CAPTURING,
            finish_capture=completed,
            if_changed=True,
        )
