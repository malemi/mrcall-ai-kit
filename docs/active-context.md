---
doc_baseline_commit: 5de5a54d781f9b4d23821b393abd04ff3976b8f1
doc_baseline_date: 2026-08-15
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness v3 is implemented and committed across Claude Code, Codex, and
OpenCode. The full contract lives in
[`documentation-harness.md`](documentation-harness.md); enforcement of the
living-context shape is three-layered, with the heading half mechanical in
`doc-check.py`. `doc-end` delegates to pinned-model workers (`worker-sonnet`
mechanical, `worker-opus` verification) where the environment provides them;
gathering the session signal and deciding what is current stay non-delegable.
All `doc-*` workflows require an exact `harness_version` match before doing
work.

The work-trace rule is in force (2026-08-14): orchestrated or multi-session
work creates `docs/briefs/YYYY-MM-DD-<slug>.md` +
`docs/execution-plans/YYYY-MM-DD-<slug>.md` before execution, with lifecycle
only in the plan's `status` frontmatter. Four enforcement points: `doc-create`
ships the briefs directory and writes the one-line pointer into the configured
index (the trigger binding — it fires exactly in harness repos); `doc-end`
Phase 3 creates a missing pair in-session and must fill a mandatory *work
trace* output slot; a delegated `doc-critic` reports a `TRACE:` finding
instead of inventing content; `doc-check.py` reports undated trace filenames
as an advisory. The OpenCode orchestrator persists this pair natively (its
private `docs/plans/execution.md` schema is gone) and its question templates
are in English.

The gate emits two advisory families, never affecting the exit code:
`doc_max_lines` (default 400, archive exempt) and undated work-trace
filenames. 36 checker tests pass. The root `README.md` is human-facing (82
lines: value proposition plus two-minute install; protocol internals live
only in the contract). This machine installs the kit in symlink mode, so the
installed commands and checker track the working tree with no reinstall.

## Unresolved

- None.

## Next

- Exercise `doc-create`'s v1→v2 migration path against a real v1 repository
  (not just `doc-critic`'s repair in isolation, which is already verified) to
  confirm the migration note produces the same archive-and-trim result when
  entered through the version-mismatch flow rather than invoked directly.
- On the next protocol change, bump the embedded command/checker version and
  add its explicit repository migration before releasing it.
- Rewrite `opencode/skills/orchestrator/REVIEW.md` in English, or supersede
  and archive it (logged in [`harness-backlog.md`](harness-backlog.md)).
