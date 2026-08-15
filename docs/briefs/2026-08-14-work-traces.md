# Work traces: every substantial workstream leaves a brief and a plan

**Date**: 2026-08-14 · **Plan**: [../execution-plans/2026-08-14-work-traces.md](../execution-plans/2026-08-14-work-traces.md)

## Problem

The harness defined execution plans (schema, gate, lifecycle) and mentioned
briefs once in passing, but nothing said WHEN to create either. Every command
regulated traces that already existed: `doc-check` validated them, `doc-start`
read them, `doc-end` reconciled them — creation was nobody's job. Orchestrated
work therefore routinely ran with no trace: no record of what was being
attempted, whether it finished, or whether it was ever started. The OpenCode
orchestrator was worse than silent: it persisted its own
`docs/plans/execution.md` with status in a heading — the exact pattern the
contract forbids — in a directory the harness does not index.

## Decision

Substantial work — orchestrated fan-outs, or workstreams expected to span
sessions — always creates a dated pair before execution:

- `docs/briefs/YYYY-MM-DD-<slug>.md` — what and why (no status frontmatter);
- `docs/execution-plans/YYYY-MM-DD-<slug>.md` — lifecycle in `status`
  frontmatter (`planned` = only conceived, `active`, `blocked`, `completed`,
  `superseded`).

## Design choices

- **The trigger lives in the index file.** No `doc-*` command is running at
  the moment orchestration starts, so the rule must already be in context:
  `doc-create` writes a one-line pointer into the configured index, which
  makes the rule fire exactly in repositories that use this harness and
  nowhere else (a global instruction would fire everywhere; a per-repo one
  would fire in one).
- **Enforcement mirrors the living-context shape.** `doc-end` Phase 3 creates
  a missing pair in-session (it holds the transcript); a delegated
  `doc-critic` reports the absence (`TRACE:` finding) and never invents
  content; the mechanical gate reports undated trace filenames as an
  advisory.
- **Advisory, not blocking, for naming.** A blocking filename check would
  break existing repositories and require a `harness_version` bump plus
  migration; the convention gets teeth without either.
- **The orchestrator obeys the contract.** Its private
  `docs/plans/execution.md` schema is replaced by the harness pair; plan
  status moves to YAML frontmatter.

## Out of scope

- Rewriting `opencode/skills/orchestrator/REVIEW.md` (historical review
  document, in Italian) — logged in [../harness-backlog.md](../harness-backlog.md).
- A blocking naming check (would need harness v4 plus a repository
  migration).
