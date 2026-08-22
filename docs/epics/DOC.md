# Epic DOC — Documentation & Project Tooling

Scope: `README.md`, `tools/`, `docs/`.

## Purpose

Everything about working on gCustodian rather than what it does at runtime:
setup instructions, the dev workflow docs, git hooks, and epic docs
themselves.

## Current design

- `tools/dev-docs/` holds the ChangeIt/FinishIt/PostMerge workflow docs,
  matching the convention used in MinecraftMgr/MissionImpossible/OrbisSpace.
- `tools/git-hooks/` enforces the commit-subject and branch-name conventions
  described in [../README.md](README.md); run `tools/git-hooks/install.sh`
  once per clone since `.git/hooks/` isn't tracked by git.

## Open work

- None currently.
