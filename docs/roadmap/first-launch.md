# First launch plan

Status: **proposal**, based on the repository and GitHub state on 3 November 2026. To be reviewed
and prioritised by the team.

## Goal

A platform in the spirit of Read AI: a meeting assistant joins a Google Meet call, a transcript is
produced, structured minutes are drafted by AI, and people review, validate, search and export them
on a web platform. The assistant is started from a **browser extension** that controls the Vexa bot
([ADR 0002](../decisions/0002-extension-controls-the-vexa-bot.md)).

Baraza keeps its own principles: the assistant is visible, participants are informed, minutes are
a **draft until a human validates them**, and nothing is invented (missing owners and dates read
"Not specified").

The screens are in [docs/mockups/baraza-product.html](../mockups/baraza-product.html) when that file
is committed.

## Scope

| In the first launch | Out of the first launch |
|---|---|
| Google Meet capture through the assistant, started from the extension or a pasted link | Calendar integration and automatic joining |
| Live transcript, status and stop | Teams and Zoom |
| AI minutes draft with sources, human editing and validation | Questions answered across all meetings (search is in) |
| Library, search, open actions, series | Capturing audio in the browser (no bot) |
| Sharing with roles, export to Word, PDF and Markdown | Real-time summary during the call |
| Sign in, roles, administration, privacy settings | |

The GitHub milestone "MVP" holds 133 open issues. The first launch is a **subset** of it: the cut
line is the table above.

## Where we are

| Area | State |
|---|---|
| Segment format and ingestion | Merged. Final transcript submission, minutes retrieval and a fake capture adapter are in PR #200 (open). |
| Capture API contract | Documented in PR #196 (open). Implemented against a fake adapter in #200. |
| Vexa client and configuration | PR #197 (open). Merged with #200 on a working branch, not wired into the capture API. |
| LLM client, JSON output, anti-invention | PR #198 (open, CI failing). Lives in a separate `app/` package, not wired into `baraza`. |
| Frontend | Start screen, status, live transcript, minutes (simulated), DAH Labs design. No authentication, library, editor or export. |
| Authentication, roles, extension | Not started. |
| Database migrations | Not set up (tables are created on first use). |
| Real Google Meet capture | Never run. Docker could not be started on the main dev machine. |

## Work packages and order

Each package lists what it needs first. Issue numbers refer to the GitHub milestone "MVP".

| # | Package | Contents | Needs |
|---|---|---|---|
| 0 | **Stabilise** | Review and merge #196, #197, #198 (after CI fix), #200. Agree how `POST /captures` starts a Vexa capture (direct adapter call versus worker job). One `baraza` package, no duplicate `app/`. | none |
| 1 | **Capture end to end** | Wire `VexaAdapter` into the capture API; meeting states and transitions (#77); URL validation (#98); participant information before capture (#106); one real test meeting with consent. | 0 |
| 2 | **Minutes pipeline** | LLM client (#81), JSON output (#82), anti-invention (#83), prompt-injection mitigation (#84), generation job (#89), minutes API (#135). | 0 |
| 3 | **Platform foundations** | Database models and Alembic (#51-#54), sign in and roles (#63-#68, #158), authorization (#67), consistent errors (#56). | 0 |
| 4 | **Review and validation** | Minutes editor (#140), transcript viewer with links to sources (#141), speaker renaming (#138, #142), validation flow (#143). | 2, 3 |
| 5 | **Extension** | New issues to create: extension scaffold (Manifest V3, side panel), token pairing with the platform, start and stop from the Meet tab, status and live transcript. | 1, 3 |
| 6 | **Library, search, series** | Library with search (#150, #151, #155), open actions (#152, #156), series and carry-over (#153, #154). | 3, 4 |
| 7 | **Export and sharing** | Markdown, Word, PDF (#144-#147), sharing and permissions (#161), notification (#148). | 4 |
| 8 | **Privacy and security** | Threat model (#73), retention and deletion (#101-#103), access log (#91), encryption at rest (#76), security review before a pilot (#99). | 3, in parallel |
| 9 | **Deployment and docs** | Production Compose (#164), HTTPS (#74), backups (#167), quick start and user guide (#173, #175). | 8 |

## Critical path

`0 → 1` (capture) and `0 → 2` (minutes) can run in parallel. Both feed `4` (review). `3`
(authentication) gates `4`, `5` and `6`, so it should start right after `0`. The extension (`5`)
comes late because it needs both a working capture and authentication.

```
0 Stabilise ─┬─ 1 Capture ───────────────┐
             ├─ 2 Minutes ──┬─ 4 Review ─┼─ 6 Library ─ 7 Export
             └─ 3 Platform ─┴────────────┴─ 5 Extension
                    8 Privacy and security runs alongside; 9 Deploy last
```

## Risks

- **Size.** The subset above is still large for the milestone date of 1 December 2026 with four
  people. If dates are fixed, the first thing to cut is series (6) and sharing (7), keeping a
  single-user platform with export.
- **Vexa is not proven yet.** No real meeting has been captured. Package 1 should produce evidence
  early, before the extension and the library are built on top.
- **Authentication gates a lot.** Starting it late would block the extension and the platform.
- **Two code lines.** The LLM work (#198) and the Vexa work (#197) are developed separately from the
  main flow; the longer they stay apart, the more the integration costs.
- **Docker on the dev machines.** Several packages need Redis and PostgreSQL. A machine where
  Docker cannot start slows testing.
