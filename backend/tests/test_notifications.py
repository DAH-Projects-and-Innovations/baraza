"""Emails about the draft (issues #148, #71): content-free, never blocking."""

import asyncio
import socketserver
import threading
from email import message_from_bytes
from email.message import EmailMessage
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_regenerate import FIRST, BrokenLLM
from test_sprint3_flow import REQUEST, RecordingQueue, flow, start  # noqa: F401

from baraza.config import Settings
from baraza.core.meeting_record import Meeting
from baraza.core.notifications import build_message, notify, send_smtp
from baraza.llm.client import FakeLLMClient
from baraza.storage.sql import SqlMeetingStore
from baraza.worker import generate_minutes_task

Flow = tuple[TestClient, SqlMeetingStore, RecordingQueue]


def settings(**kw) -> Settings:
    base = {"smtp_host": "mail.test", "smtp_from": "Baraza <baraza@example.org>"}
    return Settings(**{**base, **kw})


def meeting(**kw) -> Meeting:
    data = {
        "capture_id": "m1",
        "title": "Budget\nreview",
        "meeting_url": "https://meet.google.com/abc-defg-hij",
        "adapter": "fake",
        "participants_informed": True,
        "created_by": "awa@example.org",
    }
    return Meeting(**{**data, **kw})


class Outbox:
    def __init__(self, fail_times: int = 0) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self, _settings: Settings, message: EmailMessage) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("mail server down")
        self.sent.append(message)


def test_the_email_holds_only_the_title_and_a_link() -> None:
    message = build_message(
        meeting(), "ready", settings(public_url="https://baraza.test/"), "a@b.c"
    )
    assert message["To"] == "a@b.c"
    assert message["Subject"] == "Draft minutes ready: Budget review"  # no line break from a title
    body = message.get_content()
    assert "https://baraza.test/meetings/m1" in body and "Budget review" in body
    assert len(body) < 300  # no room for minutes or transcript text


def test_the_language_follows_the_transcript(transcript) -> None:
    french = transcript.model_copy(update={"language": "fr"})
    message = build_message(meeting(transcript=french), "error", settings(), "a@b.c")
    assert "n'a pas pu être généré" in message["Subject"]


def test_nothing_is_sent_without_a_server_or_an_email_recipient() -> None:
    outbox = Outbox()
    assert asyncio.run(notify(meeting(), "ready", Settings(), sender=outbox)) is False
    anonymous = meeting(created_by="local-user")
    assert asyncio.run(notify(anonymous, "ready", settings(), sender=outbox)) is False
    assert (
        asyncio.run(notify(meeting(created_by=None), "ready", settings(), sender=outbox)) is False
    )
    assert outbox.calls == 0


def test_a_flaky_server_is_retried_then_given_up_quietly() -> None:
    flaky = Outbox(fail_times=2)
    assert asyncio.run(notify(meeting(), "ready", settings(), sender=flaky, retry_delay_s=0))
    assert len(flaky.sent) == 1
    down = Outbox(fail_times=99)
    assert not asyncio.run(notify(meeting(), "ready", settings(), sender=down, retry_delay_s=0))
    assert down.calls == 3  # first try and two retries


def test_smtp_must_be_encrypted_unless_explicitly_allowed() -> None:
    with pytest.raises(ValidationError):
        settings(smtp_starttls=False)
    assert settings(smtp_starttls=False, smtp_allow_insecure=True).smtp_host == "mail.test"
    assert Settings(smtp_starttls=False).smtp_host == ""  # no server: nothing to protect


def run_worker(store: SqlMeetingStore, capture_id: str, llm, outbox: list) -> None:
    async def mailer(m, kind, _settings) -> None:
        outbox.append((kind, m.title, m.created_by))

    asyncio.run(
        generate_minutes_task({"meeting_store": store, "llm": llm, "mailer": mailer}, capture_id)
    )


def test_the_worker_notifies_the_person_who_started_the_meeting(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = start(client)
    assert asyncio.run(store.get(capture_id)).created_by == "local-user"
    client.post(f"/captures/{capture_id}/stop")
    sent: list = []
    run_worker(store, capture_id, FakeLLMClient(FIRST), sent)
    assert sent == [("ready", "Fictional sprint review", "local-user")]


def test_a_failed_generation_sends_the_error_email(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")
    sent: list = []
    run_worker(store, capture_id, BrokenLLM(), sent)
    assert [kind for kind, *_ in sent] == ["error"]


def test_a_broken_mailer_does_not_change_the_generation(flow: Flow) -> None:  # noqa: F811
    client, store, _ = flow
    capture_id = start(client)
    client.post(f"/captures/{capture_id}/stop")

    async def broken(*_args) -> None:
        raise RuntimeError("boom")

    asyncio.run(
        generate_minutes_task(
            {"meeting_store": store, "llm": FakeLLMClient(FIRST), "mailer": broken}, capture_id
        )
    )
    assert client.get(f"/captures/{capture_id}").json()["status"] == "done"


class _Capture(socketserver.StreamRequestHandler):
    """A tiny SMTP server that records one message: enough to see a real send."""

    received: ClassVar[list[bytes]] = []

    def handle(self) -> None:
        def reply(line: str) -> None:
            self.wfile.write(f"{line}\r\n".encode())

        reply("220 test ESMTP")
        data_mode, chunks = False, []
        while line := self.rfile.readline():
            if data_mode:
                if line == b".\r\n":
                    _Capture.received.append(b"".join(chunks))
                    data_mode = False
                    reply("250 queued")
                else:
                    chunks.append(line)
                continue
            command = line[:4].upper()
            if command in (b"EHLO", b"HELO"):
                reply("250 test")
            elif command == b"DATA":
                data_mode = True
                reply("354 go")
            elif command == b"QUIT":
                reply("221 bye")
                return
            else:
                reply("250 ok")


def test_a_real_smtp_server_receives_the_message() -> None:
    _Capture.received.clear()
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Capture) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        config = settings(
            smtp_host="127.0.0.1", smtp_port=port, smtp_starttls=False, smtp_allow_insecure=True
        )
        message = build_message(meeting(), "ready", config, "awa@example.org")
        send_smtp(config, message)
        server.shutdown()
    received = message_from_bytes(_Capture.received[0])
    assert received["To"] == "awa@example.org"
    assert "meetings/m1" in received.get_payload()
