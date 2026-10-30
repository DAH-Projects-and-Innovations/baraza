"""Reusable contract: provide `adapter` and `meeting_url` fixtures and mock its external service.

The fixture must script waiting -> capturing -> processing and a complete transcript,
plus a successful stop response. No real conferencing credentials are needed.
"""

from baraza.adapters.base import CaptureAdapter, CaptureStatus


class CaptureAdapterContract:
    async def test_capture_contract(self, adapter: CaptureAdapter, meeting_url: str):
        assert adapter.name
        assert adapter.capabilities().platforms
        capture_id = await adapter.start(meeting_url)
        assert isinstance(capture_id, str) and capture_id
        assert await adapter.status(capture_id) == CaptureStatus.WAITING_ADMISSION
        assert await adapter.status(capture_id) == CaptureStatus.CAPTURING
        await adapter.stop(capture_id)
        assert await adapter.status(capture_id) == CaptureStatus.PROCESSING
        transcript = await adapter.fetch_transcript(capture_id)
        assert transcript.source_adapter == adapter.name
        assert transcript.segments
        assert all(s.speaker and s.end >= s.start >= 0 for s in transcript.segments)
