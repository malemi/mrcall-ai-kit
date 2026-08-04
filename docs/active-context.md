---
doc_baseline_commit: 838eb785396cfb9063c2af3d3e57025041c383e0
doc_baseline_date: 2026-08-04
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness version 2 is implemented across Claude Code, Codex, and OpenCode.
Pruned `active-context.md` narrative now moves to `active-context-archive.md`
(dated, newest first, verbatim, never read by `doc-start`) instead of being
discarded: `doc-end` Phase 3 archives it proactively every session, and
`doc-critic` independently checks the file's shape and repairs it directly
whenever it drifts — the backstop for the exact failure the plain instruction
alone did not prevent (a real downstream repo's `active-context.md` grew from
~120 to ~1500 lines over two months of sessions that each said "consolidate").
The repair was verified against a real scratch fixture, byte-for-byte zero
information loss. The durable contract is in
[`documentation-harness.md`](documentation-harness.md); 18 checker tests + the
Codex install layout test pass.

All `doc-*` workflows now require an exact `harness_version` match before doing
work. Directional failures distinguish a stale installed kit from repository
docs that need an explicitly authorized migration.

Codex receives native user-level skills under `$HOME/.agents/skills`; install
and uninstall were verified in disposable HOME directories in both copy and
symlink modes.

The OpenRouter Auto Router experiment is complete. The working OpenCode agent
model ID is `openrouter/openrouter/auto`, and delegation was verified
end-to-end. Retained evidence and superseded hypotheses live in
[`briefs/test-worker-auto.md`](briefs/test-worker-auto.md), not in this volatile
snapshot.

## Unresolved

- None.

## Next

- Exercise `doc-create`'s v1→v2 migration path against a real v1 repository
  (not just `doc-critic`'s repair in isolation, which is already verified) to
  confirm the migration note produces the same archive-and-trim result when
  entered through the version-mismatch flow rather than invoked directly.
- On the next protocol change, bump the embedded command/checker version and
  add its explicit repository migration before releasing it.
