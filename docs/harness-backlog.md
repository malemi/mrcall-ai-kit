# Harness Backlog

Deferred doc-harness / orchestration improvements.

## OPEN — a delegation cannot be resumed, and nobody has checked whether it could be

**Logged**: 2026-08-24. Every delegation is one-shot: the orchestrator calls
`task`, the worker returns, and any follow-up is a fresh call with a fresh
prompt. Nothing under `opencode/` uses a resume primitive — no agent, command
or skill mentions resuming a worker by task id — and whether OpenCode's `task`
tool supports one has never been checked against the tool's own schema. Until
someone checks, a worker that stops one step short costs a full re-run. The
check is cheap and it settles whether this is a gap in the protocol or a limit
of the platform.

## OPEN — nothing checks an installed machine for an agent whose preloaded skill is missing

**Logged**: 2026-09-25. A Claude Code agent that preloads a skill runs without
it, silently, when the skill is not installed
([known issue](known-issues-and-solutions.md#a-claude-role-agent-runs-without-its-shared-rules-when-its-skill-is-missing)).
`tests/test_agent_profiles.sh` checks a fresh install in a temporary home, which
always installs the skill. It does not check a machine whose install predates
the agent's `skills:` line, and neither does anything else: `/ai-help` lists
agents and skills side by side without saying that an agent names a skill that
is absent. The cheapest closing check is `ai-help.sh` flagging such an agent.

## OPEN — a later install with `--on-exist overwrite` forgets a recorded backup

**Logged**: 2026-09-25. `uninstall.sh --restore-backups` restores the backup
recorded on a path's last install-log line. A later `install.sh --on-exist
overwrite` writes a line with an empty backup column for the same path, so an
operator's file that an earlier `--on-exist backup` install moved aside stays
at its backup path after an uninstall. `/ai-budget` keeps the recorded backup
when it rewrites a line; the installer does not. Found by the M5 review of the
budget-driven model resolution plan. Closing it: `uninstall.sh` looks back to
the last recorded backup for the path, or an overwrite install carries it
forward.

## OPEN — a client can skip the complete documentation lifecycle

**Logged**: 2026-10-05. Native Codex tests can complete an explicitly requested
whole-lifecycle bypass without creating a completion record or receiving a
host denial. The completion CLI refuses missing or stale evidence only when
invoked; model instructions and stored attestations do not force invocation.
The measured client/configuration limits are in
[`harness-runtime-support.md`](harness-runtime-support.md). Closing this gap
requires an independently supported runtime interception point with an actual
denial and compliant retry; no such control is claimed by v9.

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
- `docs/execution-plans/2026-09-22-kit-agent-layer-and-issue-visibility.md` —
  **keep whole**, 465 lines, 2026-09-28. The active plan holds the operator's
  decisions and the remaining enforcement item alongside their dependencies;
  readers need its order and boundaries together.
- `docs/execution-plans/2026-09-24-budget-driven-model-resolution.md` —
  **keep whole**, 413 lines, 2026-09-28. The completed plan records one
  six-milestone delivery sequence and its merge and rollback dependencies.
- `docs/briefs/2026-09-24-budget-driven-model-resolution.md` — **keep whole**,
  408 lines, 2026-09-28. The dated brief argues one model-resolution decision
  from measured inputs through requirements and limits.
