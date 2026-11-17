"""Emails to the person who started a meeting: the draft is ready, or something went wrong.

Privacy rule: an email holds the meeting title and a link, never any transcript or minutes text.
Sending never makes a generation fail: an unreachable mail server is logged (without content)
and the draft is still there when the person opens the app.
"""

import asyncio
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from email.utils import formatdate
from typing import Literal

import structlog

from baraza.config import Settings
from baraza.core.meeting_record import Meeting

Kind = Literal["ready", "error"]

TEXTS: dict[str, dict[Kind, tuple[str, str]]] = {
    "en": {
        "ready": (
            "Draft minutes ready: {title}",
            'The draft minutes of "{title}" are ready for your review.\n\nOpen them: {link}\n',
        ),
        "error": (
            "Minutes could not be generated: {title}",
            'The draft minutes of "{title}" could not be generated.\n\n'
            "Open the meeting to try again: {link}\n",
        ),
    },
    "fr": {
        "ready": (
            "Brouillon de compte rendu prêt : {title}",
            "Le brouillon du compte rendu de « {title} » est prêt à être relu.\n\n"
            "Ouvrir : {link}\n",
        ),
        "error": (
            "Le compte rendu n'a pas pu être généré : {title}",
            "Le brouillon du compte rendu de « {title} » n'a pas pu être généré.\n\n"
            "Ouvrir la réunion pour réessayer : {link}\n",
        ),
    },
}


def recipient_of(meeting: Meeting) -> str | None:
    """The person who started the meeting, when that is an email address."""
    who = meeting.created_by
    return who if who and "@" in who else None


def build_message(meeting: Meeting, kind: Kind, settings: Settings, to: str) -> EmailMessage:
    language = meeting.transcript.language if meeting.transcript else "en"
    subject, body = TEXTS["fr" if language == "fr" else "en"][kind]
    link = f"{settings.public_url.rstrip('/')}/meetings/{meeting.capture_id}"
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Date"] = formatdate(localtime=False)
    # Header values cannot hold line breaks: a title is user input.
    title = " ".join(meeting.title.split())
    message["Subject"] = subject.format(title=title)
    message.set_content(body.format(title=title, link=link))
    return message


def send_smtp(settings: Settings, message: EmailMessage) -> None:
    """Blocking send; run it in a thread."""
    if settings.smtp_ssl:
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_s,
            context=ssl.create_default_context(),
        )
    else:
        client = smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_s
        )
    with client:
        if settings.smtp_starttls and not settings.smtp_ssl:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        client.send_message(message)


async def notify(
    meeting: Meeting,
    kind: Kind,
    settings: Settings,
    *,
    sender: Callable[[Settings, EmailMessage], None] = send_smtp,
    retry_delay_s: float = 2.0,
) -> bool:
    """Send the email, trying a few times. Returns whether it was sent."""
    log = structlog.get_logger()
    if not settings.smtp_host:
        return False
    to = recipient_of(meeting)
    if to is None:
        return False
    message = build_message(meeting, kind, settings, to)
    attempts = settings.smtp_retries + 1
    for attempt in range(attempts):
        try:
            await asyncio.to_thread(sender, settings, message)
            return True
        except Exception:
            # No recipient, title or message in the log.
            log.warning("notification_failed", meeting_id=meeting.capture_id, attempt=attempt + 1)
            if attempt < attempts - 1:
                await asyncio.sleep(retry_delay_s * (attempt + 1))
    return False
