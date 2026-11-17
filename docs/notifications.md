# Email notifications

Baraza emails the person who started a meeting when:

- the draft minutes are ready for review (also after a regeneration);
- the draft could not be generated (or a regeneration failed and the previous draft was kept).

An email holds **the meeting title and a link, nothing else**: no transcript, no minutes, no
participant names. It is written in French when the meeting's transcript is in French, in English
otherwise. The recipient is the email of the signed in person who started the capture; with
sign in switched off (local development) nobody is emailed.

Sending never changes the outcome of a generation. The worker tries three times (two retries,
with a growing pause); if the mail server stays unreachable it logs a warning without any address,
title or text, and the draft is simply waiting in the app.

## Settings (`.env`)

| Variable | Meaning |
|---|---|
| `BARAZA_SMTP_HOST` | Mail server. Empty (default): no email is sent. |
| `BARAZA_SMTP_PORT`, `BARAZA_SMTP_USER`, `BARAZA_SMTP_PASSWORD` | Connection and login. |
| `BARAZA_SMTP_FROM` | Sender, e.g. `Baraza <no-reply@example.org>`. |
| `BARAZA_SMTP_STARTTLS` / `BARAZA_SMTP_SSL` | Encryption. One of them must stay on. |
| `BARAZA_SMTP_ALLOW_INSECURE` | `true` only for a local test server (Mailpit). |
| `BARAZA_PUBLIC_URL` | Where people open the app; the link in the email points here. |

## Looking at the emails locally

```bash
docker compose --profile mail up -d mailpit
```

Then in `.env`: `BARAZA_SMTP_HOST=mailpit`, `BARAZA_SMTP_PORT=1025`,
`BARAZA_SMTP_STARTTLS=false`, `BARAZA_SMTP_ALLOW_INSECURE=true`. The emails appear at
<http://localhost:8025>.

## Not done yet

Password-reset emails (the other use of #71) are not part of this.
