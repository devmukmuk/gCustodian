# gCustodian

Personal MCP tools for managing Gmail, Google Photos, and Google Drive from Claude Code.

Currently implemented: **Gmail** (search, read, label, archive) and a **local
Thunderbird archive** (index, search, read — read-only). Photos and Drive
will follow the same pattern under `src/gcustodian/services/` as they're
built out.

## Setup

1. **Google Cloud project**
   - Create a project at https://console.cloud.google.com/
   - Enable the Gmail API (APIs & Services → Library)
   - Create an OAuth 2.0 Client ID (Application type: **Desktop app**)
   - Download the JSON and save it as `credentials/credentials.json`

2. **Install dependencies**
   ```
   pip install -e .
   ```

3. **Authorize** (opens a browser for consent; saves `credentials/token.json`)
   ```
   python -m gcustodian.auth
   ```

4. **Register with Claude Code**
   ```
   claude mcp add gcustodian -- python -m gcustodian.server
   ```
   Reconnect/restart Claude Code and the `gmail_*` tools become available.

## Scopes

Requested scopes live in `src/gcustodian/auth.py::SCOPES`. Currently:
`gmail.readonly`, `gmail.modify` (no send/delete). Add Drive/Photos scopes there
when those services are wired up, then re-run the authorize step to re-consent.

## Thunderbird local archive

Read-only access to a local Thunderbird "Local Folders" mbox archive
(e.g. a Gmail export migrated into Thunderbird). No Google auth involved.

1. Set `GCUSTODIAN_THUNDERBIRD_PROFILE` to the Thunderbird profile
   directory — the folder containing `Mail\Local Folders`, e.g.
   `E:\archive\Thunderbird`.
2. Run `thunderbird_index` (via the MCP tool, or
   `python -c "from gcustodian.services import thunderbird; print(thunderbird.build_index())"`)
   to build the local search index at `data/thunderbird_index.sqlite`
   (gitignored, separate from the Thunderbird profile — nothing is ever
   written back into it).
3. Use `thunderbird_search` / `thunderbird_read` / `thunderbird_list_folders`.

This is intentionally read-only: tagging, priority, dedupe, and address
book management are tracked as follow-up work in
[docs/epics/TBIRD.md](docs/epics/TBIRD.md).

### Missionary weekly report

For a regular correspondent like a missionary, set `GCUSTODIAN_OWNER_EMAIL`
to your own address and run `thunderbird_missionary_report` with their name
(matched against the indexed From header, e.g. "Jackson Webb"). It builds
one row per calendar week from a start date, marking whether they sent you
anything (`received`) and whether you replied (`sent`) in that window —
weeks with neither are still listed, marked blank, rather than skipped.
This doesn't depend on any subject-line convention (real missionaries use
inconsistent, sometimes empty, subjects).

Week 1's start date comes from `data/missionaries.json` (gitignored,
gCustodian-owned — not written into Thunderbird's own address book) keyed
by the missionary's lowercase email:

```json
{
  "katelyn.thacker@missionary.org": { "start_date": "2026-08-01" }
}
```

An optional `"end_date"` bounds the last week generated (e.g. when they
return); omit it to run through today. With no entry at all, the start
date falls back to that missionary's earliest indexed message. The
metadata file's path can be overridden with `GCUSTODIAN_MISSIONARY_METADATA`
(used by the test suite; leave unset for real runs).

## Notes

- `credentials/credentials.json` and `credentials/token.json` are gitignored —
  never commit them.
- Each new service should get its own module under `src/gcustodian/services/`
  and a matching set of `@mcp.tool()` wrappers in `server.py`.
