# gCustodian Epics

The canonical **Epic** codes used for issue tracking on
[github.com/devmukmuk/gCustodian](https://github.com/devmukmuk/gCustodian).
These codes are also the registry read by `config/git/epics.txt` and enforced
by the `commit-msg` and `pre-push` git hooks in `tools/git-hooks/` — see that
folder's `install.sh`.

| Code | Epic | Design doc |
|------|------|------------|
| AUTH | OAuth & Credentials — `src/gcustodian/auth.py`, `credentials/` | [AUTH.md](AUTH.md) |
| GMAIL | Gmail Service — `src/gcustodian/services/gmail.py` | [GMAIL.md](GMAIL.md) |
| PHOTOS | Google Photos Service — `src/gcustodian/services/photos.py` (planned) | [PHOTOS.md](PHOTOS.md) |
| DRIVE | Google Drive Service — `src/gcustodian/services/drive.py` (planned) | [DRIVE.md](DRIVE.md) |
| SRV | MCP Server Wiring — `src/gcustodian/server.py`, tool registration | [SRV.md](SRV.md) |
| DOC | Documentation & Project Tooling — `README.md`, `tools/`, `docs/` | [DOC.md](DOC.md) |

## Conventions enforced by the git hooks

**Commit subject:**
```
<type>(<CODE>): <short description>
```
Example: `feat(GMAIL): add label-by-sender search helper`

**Branch name:**
```
<type>/<issue>-<CODE>-<short-description>
```
Example: `feat/5-GMAIL-add-label-by-sender-search-helper`

**Allowed types:** `feat fix docs test refactor perf build chore`

Adding a new epic: append the code to `config/git/epics.txt` and add a row to
the table above (and a design doc if it's substantial enough to warrant one).
