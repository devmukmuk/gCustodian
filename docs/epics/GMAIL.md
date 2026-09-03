# Epic GMAIL — Gmail Service

Scope: `src/gcustodian/services/gmail.py`.

## Purpose

Wraps the Gmail API for the MCP tools exposed in `server.py`: search, read,
label, archive, and draft creation.

## Current design

- Read-only search/read plus label/archive — no send or permanent delete.
  Matches the `gmail.readonly` + `gmail.modify` scopes requested in
  [AUTH.md](AUTH.md).
- `create_draft` (tool: `gmail_create_draft`) builds a `MIMEText` message
  and calls `drafts().create` only — it writes to the Drafts folder for the
  user to review and send by hand, and never calls `drafts().send` or
  `messages().send`. Backed by the `gmail.compose` scope (draft-only; see
  [AUTH.md](AUTH.md)). Added for Orbit's business-outreach flow, which needs
  drafts prepared for manual review before sending.
- `list_messages` fetches metadata headers only (From/Subject/Date); full
  body is fetched separately by `get_message` to keep search results small.
- `archive_message` is just `modify_labels(remove=["INBOX"])` — Gmail has no
  separate "archive" API call.

## Open work

- Still no send capability by design. `gmail.compose` was added for
  draft creation only; sending remains out of scope and would be a
  separate, explicitly-scoped decision if a real use case ever needs it.
