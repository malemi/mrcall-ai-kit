# Harness Backlog

Deferred doc-harness / orchestration improvements.

## OPEN — reviewer model metadata is not in the selection table

**Logged**: 2026-08-24. `opencode/agents/reviewer.md` pins
`model: opencode/claude-sonnet-5`, but no table in `llms.md` records that
non-worker model choice. The reviewer is absent from the strict fast path but
mandatory at every substantial-work lifecycle gate. Its pinned model should
still be visible in the metadata source when that table is next revised.

## OPEN — a delegation cannot be resumed, and nobody has checked whether it could be

**Logged**: 2026-08-24. Every delegation is one-shot: the orchestrator calls
`task`, the worker returns, and any follow-up is a fresh call with a fresh
prompt. Nothing under `opencode/` uses a resume primitive — no agent, command
or skill mentions resuming a worker by task id — and whether OpenCode's `task`
tool supports one has never been checked against the tool's own schema. Until
someone checks, a worker that stops one step short costs a full re-run. The
check is cheap and it settles whether this is a gap in the protocol or a limit
of the platform.

## OPEN — scope-guard installs its Claude command to a destination twice

**Logged**: 2026-09-08. `install.sh:293` sweeps `claude/commands/` wholesale
under the router feature, and `:303` adds `claude/commands/scope-guard.md`
explicitly under the scope-guard feature. Selecting both with `--on-exist
backup` therefore installs the file, then moves it to `.bak` on the second pass
and installs it again, leaving one stray backup and two manifest entries for one
destination. Present at `HEAD` and unrelated to the feature that surfaced it;
the `shortcuts` feature avoids the same shape by keeping its sources outside
every swept directory. The fix is the `$DO_DOC ||` guard pattern already used
for `worker-fable` at `:296`, or moving the source out of the sweep.

## Oversized docs — reviewed

One line per document the gate's oversized advisory has named, with the verdict
that settled it. A document listed here is never asked about again.

- `docs/documentation-harness.md` — **split**, 2026-08-25. The gate named it at 457
  lines in the working tree, mid-session, and the split was committed before
  that state ever was — so git shows it at 349 and no commit will corroborate
  the number. It had grown a second subject: the opt-in model router, its session memory,
  the rotation hand-off, and the worker-report budget. Those moved to
  `docs/model-router.md`, leaving the harness contract comfortably under the
  limit. The
  split is by subject and not by size — the gate and the `/doc-*` contract apply
  whether or not the router is installed, so a session that wants to know what
  `/doc-start` does should not pay for the delegation machinery.
- `docs/briefs/2026-08-24-harness-context-economics.md` — **keep whole**, 555
  lines. It is a dated brief: the record of one analysis, argued end to end, and
  its verdict is already stated in its own opening. Splitting an argument leaves
  two halves that each read as incomplete, and nothing here is a log.
- `docs/execution-plans/2026-08-26-scope-guard.md` — **keep whole**, 416 lines,
  2026-08-30. It is one active implementation plan whose acceptance dependencies
  run from runtime capability proof through adapters, installation, harness
  migration, and real-client verification. It is read by phase; splitting it
  would hide cross-phase gates and require traversal across multiple plans.
