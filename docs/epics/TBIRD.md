# Epic TBIRD — Thunderbird Local Archive

Scope: `src/gcustodian/services/thunderbird.py`.

## Purpose

Read access to a local Thunderbird "Local Folders" mbox archive (in this
case, a Gmail export migrated into Thunderbird) — indexing, search, and
full-message reads, exposed as MCP tools in `server.py`.

## Current design

- Read-only. Nothing is ever written back into the Thunderbird profile.
  The profile is a live one — Thunderbird may be running and holding those
  files — so this epic treats it as read-only foreign data, not something
  gCustodian owns.
- Profile root comes from the `GCUSTODIAN_THUNDERBIRD_PROFILE` env var (no
  hardcoded default — the path is machine-specific). Mail lives under
  `<profile>/Mail/Local Folders`.
- A local SQLite index (`data/thunderbird_index.sqlite`, gitignored) is
  built by walking the mbox files with the stdlib `mailbox` module. This
  index is entirely gCustodian's own state, separate from Thunderbird's own
  `.msf` caches — refreshing or deleting it never affects Thunderbird.
- `thunderbird_read` re-opens the specific mbox file on demand rather than
  caching bodies in the index, to keep the index small and avoid staleness.
- `thunderbird_missionary_report` cross-references one sender's indexed
  "Week N" updates against `GCUSTODIAN_OWNER_EMAIL`'s outgoing mail to that
  sender, to show which weeks got a reply. The index has no To/Cc columns,
  so the outgoing side is found by scanning the raw mbox archive directly
  (bounded to the months the weekly updates span, for speed).

## Open work

- Tag/priority (`X-Mozilla-Keys` / `X-Mozilla-Status2` header rewrites via
  `mailbox.mbox` reassignment), duplicate detection + delete/move by
  `Message-ID`, and address book CRUD against `abook.sqlite` are deliberately
  deferred. When built, every mutating tool must check for a running
  `thunderbird.exe` process and refuse if found, since these operations
  write into files a live Thunderbird instance may hold open.
