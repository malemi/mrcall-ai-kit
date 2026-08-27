# docs/

<!-- doc-scope:start -->
Scope: Routing index for transversal documentation; repository inventory and ownership remain in the configured root index.
<!-- doc-scope:end -->

Index of transversal docs for this repo. The repo overview, roles, and
ownership live only in the index file — see [`../CLAUDE.md`](../CLAUDE.md).
Do not duplicate that inventory here.

## Volatile

- [`active-context.md`](active-context.md) — last done / in progress / next
  as a current snapshot, never a session log.
- [`active-context-archive.md`](active-context-archive.md) — pruned session
  narrative, dated, newest first; cold storage, never read at session start.
- [`execution-plans/`](execution-plans/) — machine-readable multi-step plans.
- [`briefs/`](briefs/) — dated what/why records of workstreams, each paired
  with an execution plan (`YYYY-MM-DD-<slug>.md`).

## Durable

- [`principles.md`](principles.md) — what is allowed to exist, in code and in
  docs: the uncertainty-reduction rule and the log exemption.
- [`documentation-harness.md`](documentation-harness.md) — contract, gates,
  plan states, baseline semantics, and living-document rules.
- [`scope-guard.md`](scope-guard.md) — scope declaration format, runtime guard
  behavior, capability levels, and known bypasses.
- [`model-router.md`](model-router.md) — the opt-in model router: session
  memory, rotation and hand-off, and the worker-report budget.
- [`known-issues-and-solutions.md`](known-issues-and-solutions.md) — recurring
  verified problems and their fixes.
- [`harness-backlog.md`](harness-backlog.md) — unresolved harness work only.
- [`quality-grades.md`](quality-grades.md) — recorded quality assessments.

Other durable docs are added only when the knowledge exists; the harness does
not fabricate architecture, conventions, or system rules as placeholders.
