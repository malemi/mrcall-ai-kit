---
doc_baseline_commit: df40f9ae1158aa4037c23b76a967c92871518d4a
doc_baseline_date: 2026-08-01
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness version 1 is implemented across Claude Code, Codex, and OpenCode. Its
mechanical gate recursively covers the complete documentation tree, validates
profile and plan metadata, and reports baseline integrity separately from
semantic truth. The durable contract is in
[`documentation-harness.md`](documentation-harness.md); 14 checker tests pass.

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

- On the next protocol change, bump the embedded command/checker version and
  add its explicit repository migration before releasing it.
