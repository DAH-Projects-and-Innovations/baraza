# ADR 0002: The browser extension controls the Vexa bot

- **Status**: proposed (to be validated by the team)
- **Date**: 2026-11-03
- **Builds on**: [ADR 0001](0001-capture-approach-vexa.md)

## Context

The first launch of Baraza is a platform in the spirit of tools such as Read AI: a meeting
assistant joins the call, a transcript is produced, and structured minutes are drafted, reviewed and
validated on a web platform.

The assistant should be easy to start from where the meeting happens, so it is delivered as a
**browser extension**. Two designs are possible for that extension:

| Option | How it captures | Consequences |
|---|---|---|
| A. Remote control of the Vexa bot | The extension asks the Baraza API to start or stop the assistant. The assistant joins Google Meet as a participant. | Reuses ADR 0001. A visible, named participant appears in the call. The extension carries no audio. |
| B. Capture in the browser | The extension records the tab and microphone and uploads the audio. | No participant appears in the call. Needs browser audio capture, server-side transcription of uploaded audio, and a different consent story. |

## Decision

Use **option A**. The extension is a **thin client** of the Baraza API:

- it starts and stops a capture by calling the capture endpoints
  ([contract](../api/captures.md)), with the Meet link of the current tab;
- it shows the capture status and the live transcript in a side panel, using the same endpoints as
  the web platform;
- it links to the platform for everything else (library, editor, validation, export).

The assistant is a bot managed by the backend (`VexaAdapter`), not by the browser. It joins as a
visible participant with a clear name.

Capturing audio in the browser (option B) is **not** part of the first launch. It can be studied
later as another capture adapter, without changing the core.

## Why

- Everyone in the call can see that the assistant is present, which keeps consent honest and
  simple. A bot in the participant list is transparency, but it is not consent by itself: the
  organizer still confirms that participants were informed.
- No audio passes through the user's browser, so the extension needs few permissions.
- The core stays platform-agnostic: Teams and Zoom only add capture adapters.
- One backend path to build, test and secure, shared by the extension and the web platform.

## Consequences

- **Authentication is required before the extension ships.** The extension must act as a signed-in
  user. Proposal: a pairing flow where the signed-in platform issues a scoped, revocable token to
  the extension. To be designed with the authentication work.
- **Minimal permissions.** The extension needs access to the Baraza API origin and to the Meet tab
  URL and title only. It does not read the call content and does not capture audio.
- **The capture API is the contract.** Any change to it must keep the extension and the web
  frontend working. Document changes in `docs/api/captures.md`.
- **Distribution.** Chrome first (Manifest V3, side panel). Publishing to the Chrome Web Store has
  its own privacy review, to plan. Other browsers later.
- **Google Meet only at first.** Teams and Zoom come with their adapters, after the first launch.
- The Vexa service must be deployed and reachable by the backend (see `docs/vexa-backend.md` once
  merged).

## Open points

- Pairing and token lifetime between the platform and the extension.
- What the extension shows when the assistant is not admitted to the meeting, or when the Meet link
  belongs to another organization.
- Whether the side panel reuses the platform's React components or is built separately.
