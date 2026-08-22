# Epic DRIVE — Google Drive Service

Scope: `src/gcustodian/services/drive.py` (not yet created).

## Purpose

Will wrap the Google Drive API for managing documents/files, following the
same pattern as [GMAIL.md](GMAIL.md): a plain module of functions under
`services/`, wired up as `@mcp.tool()`s in `server.py`.

## Current design

Not started. When picked up: add the needed scopes to `auth.py::SCOPES` and
re-run the authorize step before writing any tool code.

## Open work

- Everything — no implementation yet.
