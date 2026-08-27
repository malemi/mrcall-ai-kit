---
doc_baseline_commit: 4d04b3c01c2873d9567b9bbf58baf84fd8c5760e
doc_baseline_date: 2026-08-25
---

# Active Context

<!-- doc-scope:start -->
Scope: Volatile snapshot of current verified state, unresolved work, and immediate next actions; never session history or durable design.
<!-- doc-scope:end -->

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness v4 migration and the optional scope guard are being implemented under
the [`scope-guard brief`](briefs/2026-08-26-scope-guard.md) and
[`execution plan`](execution-plans/2026-08-26-scope-guard.md). The v4
documentation contract requires one canonical scope declaration on the
configured index, `docs/README.md`, and this volatile snapshot; declarations
elsewhere are optional but mechanically validated when present.

The v3 context-economics and router contracts remain documented in
[`documentation-harness.md`](documentation-harness.md) and
[`model-router.md`](model-router.md). The scope-guard implementation has not yet
passed the required real-client acceptance tests, so no Claude Code, Codex, or
OpenCode adapter is currently described as working.

## Unresolved

- Scope-guard capability levels, event ordering, subagent behavior, and bypasses
  still require real-client verification in all three runtimes.
- A routed session can still skip creation of its instructed session-memory
  file; the existing directive is not deterministic enforcement.

## Next

- Complete the scope-guard implementation plan, then run the installed clients
  through the same activation and write flows operators use.
- Record measured capability levels and limitations in
  [`scope-guard.md`](scope-guard.md) without promoting unit-test results to
  runtime proof.
- Exercise the explicit v3-to-v4 `doc-create` migration on a disposable real
  repository; `doc-start` and `doc-end` must never migrate it implicitly.
