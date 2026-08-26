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

## Notes

- `credentials/credentials.json` and `credentials/token.json` are gitignored —
  never commit them.
- Each new service should get its own module under `src/gcustodian/services/`
  and a matching set of `@mcp.tool()` wrappers in `server.py`.
