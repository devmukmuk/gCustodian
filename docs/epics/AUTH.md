# Epic AUTH — OAuth & Credentials

Scope: `src/gcustodian/auth.py`, `credentials/`.

## Purpose

Handles the Google OAuth flow shared by every service (Gmail now, Photos/Drive
later): loading cached credentials, refreshing expired tokens, and the
one-time interactive consent flow.

## Current design

- `SCOPES` in `auth.py` is the single source of truth for what's requested.
  Adding a service means appending its scopes there and re-running
  `python -m gcustodian.auth` to re-consent.
- Currently requested scopes:
  - `gmail.readonly` — search and read messages.
  - `gmail.modify` — label and archive messages.
  - `gmail.compose` — create drafts only (no send). Added for the
    `gmail_create_draft` tool; see [GMAIL.md](GMAIL.md). `gmail.compose`
    grants draft create/update/delete but not sending — sending would need a
    further, separately-scoped decision.
- `credentials/credentials.json` (OAuth client) and `credentials/token.json`
  (cached user token) are both gitignored — never commit them.
- `get_credentials()` raises with a clear message if `token.json` doesn't
  exist yet, rather than trying to launch the interactive flow itself — that
  flow needs a browser and shouldn't run implicitly from a tool call.

## Open work

- No automatic re-consent prompt when scopes change; the error message just
  points at running `python -m gcustodian.auth` again.
