# Authentication

Baraza needs a signed in person for everything except `GET /health` and the sign in routes.
This is the first step: accounts created by an administrator, one workspace, no roles.

## How it works

- **Sign in:** `POST /auth/login` with an email and a password. The API answers with a
  session cookie: `baraza_session`, `HttpOnly` (scripts cannot read it), `SameSite=Lax`, and
  `Secure` everywhere except `BARAZA_ENV=development`. It lasts 14 days.
- **Sessions are kept on the server.** Only the SHA-256 of the token is stored, so a copy of the
  database does not give out live sessions. Signing out, changing the password, resetting it or
  deactivating the person ends the sessions.
- **Passwords** are hashed with scrypt (standard library, no extra dependency). At least 12
  characters, at most 128, not the email, not a single repeated character.
- **A wrong password and an unknown email look the same** (same answer, same cost), so the API
  does not say which addresses have an account.
- **Guessing is slowed down:** after 5 failures for one email from one address, sign in pauses for
  15 minutes (`429` with `Retry-After`). It is kept in memory, per API process: put a shared
  store behind it before running several instances.
- **Writes from another page are refused.** A browser always names its origin on a write; if it
  is not in `BARAZA_CORS_ORIGINS` the request gets `403`. `SameSite=Lax` alone does not stop
  another page on the same site.

## Routes

| Route | |
|---|---|
| `POST /auth/login` | `{email, password}`. Sets the cookie. `401` wrong credentials, `429` paused. |
| `POST /auth/logout` | Ends the session. Always `204`. |
| `GET /auth/me` | Who is signed in, or `401`. |
| `POST /auth/password` | `{current_password, new_password}`. Signs your other sessions out. |

The frontend sends `credentials: "include"`. The browser needs the API and the frontend to be on
the same *site* (for example `app.example.org` and `api.example.org`, or two ports on
`localhost`): a cookie is not sent to an unrelated site. Put the frontend origin in
`BARAZA_CORS_ORIGINS`.

## Creating the first person

There is no public sign up. An administrator creates accounts on the server:

```bash
docker compose exec api python -m baraza.cli create-user --email awa@example.org --name "Awa Example"
docker compose exec api python -m baraza.cli reset-password --email awa@example.org
docker compose exec api python -m baraza.cli deactivate-user --email awa@example.org
```

The password is asked on the terminal (twice), or read from standard input when it is piped. It
is never a command argument, so it stays out of the shell history. The migration that creates
the tables (`0004_users_and_sessions`) runs with the other migrations when the stack starts.

## Settings

| Variable | Default | |
|---|---|---|
| `BARAZA_AUTH_ENABLED` | `true` | `false` only for a local rehearsal. Refused unless `BARAZA_ENV=development`. |
| `BARAZA_SESSION_TTL_DAYS` | `14` | |
| `BARAZA_COOKIE_SECURE` | unset | Unset: secure except in development. Set it to `true` behind a proxy that ends TLS. |
| `BARAZA_LOGIN_MAX_FAILURES` | `5` | |
| `BARAZA_LOGIN_LOCKOUT_MINUTES` | `15` | |

## What it does not do yet

- **No invitations and no sign up page.** People are created from the command line.
- **No roles and no per-meeting rules.** Everyone who can sign in sees every meeting of the
  workspace and can validate minutes. That fits one organisation's pilot, not several.
- **No two-step verification, no "forgot my password" email.** An administrator resets it.
- **No audit of who read what** (#91).
- Revisions and validation record the person's email.
- The throttle is per process, and the client address is the proxy's when behind one.
