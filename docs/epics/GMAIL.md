# Epic GMAIL — Gmail Service

Scope: `src/gcustodian/services/gmail.py`.

## Purpose

Wraps the Gmail API for the MCP tools exposed in `server.py`: search, read,
label, archive.

## Current design

- Read-only search/read plus label/archive — no send or permanent delete.
  Matches the `gmail.readonly` + `gmail.modify` scopes requested in
  [AUTH.md](AUTH.md).
- `list_messages` fetches metadata headers only (From/Subject/Date); full
  body is fetched separately by `get_message` to keep search results small.
- `archive_message` is just `modify_labels(remove=["INBOX"])` — Gmail has no
  separate "archive" API call.

## Open work

- No send capability by design; revisit only if a real use case needs it,
  and treat it as a separate, explicitly-scoped addition to SCOPES.
