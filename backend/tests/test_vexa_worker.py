from unittest.mock import AsyncMock, patch

import httpx
from arq.connections import ArqRedis

from baraza.config import Settings
from baraza.storage.captures import StoredCapture
from baraza.vexa.client import BotResponse
from baraza.worker import poll_vexa_captures, shutdown, startup


async def test_disabled_worker_does_not_open_vexa():
    context = {}
    with patch("baraza.worker.get_settings", return_value=Settings(_env_file=None)):
        await startup(context)
    assert context == {}
    await poll_vexa_captures(context)
    await shutdown(context)


async def test_poll_error_does_not_block_other_meetings():
    captures = [
        StoredCapture(
            meeting_id=str(i),
            bot=BotResponse(
                id=i,
                platform="google_meet",
                native_meeting_id="abc-defg-hij",
                status="active",
            ),
        )
        for i in range(3)
    ]
    service = AsyncMock()
    service.captures.captures.return_value = captures
    service.poll.side_effect = [httpx.ReadTimeout("private details"), ValueError("bad data"), None]
    with patch("baraza.worker.structlog.get_logger") as logger:
        await poll_vexa_captures({"vexa_service": service})
    assert service.poll.await_count == 3
    assert logger.return_value.warning.call_count == 2
    assert "private details" not in str(logger.mock_calls)


async def test_poll_dispatch_is_disabled_without_service():
    # Real Redis is not needed to check the opt-in boundary.
    from baraza.worker import enqueue_vexa_poll

    redis = AsyncMock(spec=ArqRedis)
    await enqueue_vexa_poll({"redis": redis})
    redis.enqueue_job.assert_not_awaited()
