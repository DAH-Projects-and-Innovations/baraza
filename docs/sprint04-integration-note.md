# Sprint 4 integration note

Sprint 4 (database foundation) was merged on top of the Sprint 3 adapter API. Where both
branches defined the same thing, the Sprint 3 public contract wins.

- `/captures` is served by the adapter-based router in `baraza.api.captures`
  (`CaptureAdapter`, `fake` or Vexa). The Vexa-only `/captures` router from the sprint branch
  is not mounted.
- Vexa control with durable handles moved to `baraza.api.vexa_capture`:
  `POST /meetings/{id}/capture`, `POST /meetings/{id}/capture/stop`, `GET /meetings/{id}/status`.
- Versioned minutes are read at `GET /meetings/{id}/minutes/stored`. `GET /meetings/{id}/minutes`
  still returns the draft held in the meeting record. Merge the two once the worker writes
  `MinutesService` versions.
- Tables are created only by Alembic. `0003_meeting_records` adds the MVP meeting record;
  the runtime `create_all` calls were removed. Tests build their schema with `upgrade_database`.
- The worker keeps Sprint 3 draft generation and Sprint 4 database lifecycle.
