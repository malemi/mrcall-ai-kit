---
doc_baseline_commit: c8484482564b493e50a78720516b3e49b5698954
doc_baseline_date: 2026-07-25
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

The documentation harness is being tightened so its mechanical gate covers the
complete documentation tree, validates profile and plan metadata, and reports
baseline integrity separately from semantic truth. Its durable contract is in
[`documentation-harness.md`](documentation-harness.md).

All `doc-*` workflows now require an exact `harness_version` match before doing
work. Directional failures distinguish a stale installed kit from repository
docs that need an explicitly authorized migration.

The OpenRouter Auto Router experiment is complete. The working OpenCode agent
model ID is `openrouter/openrouter/auto`, and delegation was verified
end-to-end. Retained evidence and superseded hypotheses live in
[`briefs/test-worker-auto.md`](briefs/test-worker-auto.md), not in this volatile
snapshot.

## In progress

- Bring Claude Code, Codex, and OpenCode integration plus the commands, checker,
  and documentation into agreement with the documented harness contract.

## Unresolved

- The baseline above describes the last completed reconciliation. Advance it
  only after the updated mechanical gate and semantic review both pass.

## Next

- Exercise the start, end, and bootstrap workflows in a disposable leaf
  repository and verify their user-visible output and failure paths.
- Exercise recursive checking and plan-status validation with nested fixtures.
