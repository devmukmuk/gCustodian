# CLAUDE.md

Guidance for Claude Code sessions working in this repo.

## Git workflow -- no direct commits to main

All work happens on a branch and lands via PR; never commit directly to
`main`. Three standardized workflows live in `tools/dev-docs/`:

- **ChangeIt** (`tools/dev-docs/CHANGEIT.md`) -- starting new work: create
  issue, branch, implement, commit, push, PR. Trigger word: "changeit".
- **FinishIt** (`tools/dev-docs/FINISHIT.md`) -- finalizing work already in
  progress on the current branch: commit, push, PR, then beep 3 times once
  the PR is open. Trigger words: "finishit", "ready to commit and pr".
- **PostMerge** (`tools/dev-docs/POSTMERGE.md`) -- cleanup after a PR merges:
  return to main, pull, delete the local (and remote) branch, prune. Trigger
  words: "postmerge", "post-merge", "cleanup after merge".

Read the relevant doc before running its workflow -- each one lists the
commands it's allowed to run and, just as importantly, the ones it must not
(e.g. PostMerge must never create a branch or PR; FinishIt must never switch
back to main).

Adopted 2026-08-22. Applies to new commits only; the initial scaffold commits
on main predate this policy and were not rewritten.

## Commit and branch conventions

Enforced locally by `tools/git-hooks/commit-msg` and `tools/git-hooks/pre-push`
(run `tools/git-hooks/install.sh` once per clone -- `.git/hooks/` isn't
tracked by git):

- Commit subject: `<type>(<EPIC>): <description>`
- Branch name: `<type>/<issue>-<EPIC>-<description>`
- Types: `feat fix docs test refactor perf build chore`
- Epic codes: see `config/git/epics.txt` / `docs/epics/README.md`

## Epics

`docs/epics/README.md` maps each epic code (AUTH, GMAIL, PHOTOS, DRIVE, SRV,
DOC) to the part of the project it covers.
