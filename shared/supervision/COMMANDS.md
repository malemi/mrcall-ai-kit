# Supervisor operations

Use the installed kit root, not a guessed repository skill path:

```sh
kit_root="${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}"
python3 "$kit_root/supervision/runtime.py" setup
python3 "$kit_root/supervision/runtime.py" run status
```

`setup` prepares the owned Python dependency environment; `run` executes the
CLI there. State defaults to `${XDG_STATE_HOME:-$HOME/.local/state}/mrcall-ai-kit/supervision`.
Pass `--state-dir ABSOLUTE_PATH` after `run` for isolated state. Operations with
JSON input read stdin; use a file or quoted heredoc, not shell-interpolated text.
All commands return JSON. A nonzero exit is failure; a successful delivery or
inspection does not certify the underlying task.

## Activation and task creation

`activate` takes `{ "id": "team", "session_id": "EXACT_SUPERVISOR_UUID",
"target_ids": ["EXACT_TARGET_UUID"], "runtime": "codex" }` on stdin. Use `"runtime": "claude"` for a Claude binding.
Runtime is part of immutable binding identity; every target in a binding belongs
to that runtime. Different bindings can coexist in one state root.
Use `--dry-run` to inspect the owned cron entry without enabling it. Native
identity and direct-input capability are checked. Activation twice is idempotent.
For Codex bindings, the installed native application must be running; activation does not
start or restart it.
The supervisor's own tool environment must permit access to Codex's local
control socket and the state directory. A workspace sandbox may refuse the
socket even when an external cron process can reach it. Report that concrete
prerequisite; never change a session's sandbox or approval policy automatically.

### Claude prerequisite and evidence

Claude support is currently Linux, Claude Code 2.1.296, native peerProtocol 1.
Use `claude agents --json` for exact live root IDs. Both supervisor and targets
must be running with native messaging available. `CLAUDE_CONFIG_DIR` selects the
native registry/transcripts; `--claude-path /absolute/claude` selects the executable.
Activation persists the executable/config location into the owned cron command.
No daemon, session, inbound-permission setting or Agent Team is created for you.

The adapter reads the owned registry and public JSONL histories; it never writes
native state. Its socket frame is version-sensitive and gated to the inspected
version. A successful socket write remains uncertain until a recipient user
message proves delivery. Held/refused input can require operator action in that
session; never change permissions or resend to bypass it. When new evidence is
available, explicit reconciliation can revisit an earlier uncertain observation.

`task-create` input:

```json
{
  "id": "delivery",
  "supervisor_id": "team",
  "instruction": "Check progress and redirect feasible work to verified delivery",
  "target_ids": ["EXACT_TARGET_UUID"],
  "scope": "Operator-authorized task and intervention boundaries",
  "acceptance": ["The actual user path passes; unresolved failures are explained"],
  "interval_seconds": 600,
  "limits": {"provenance": "Operator message reference; defaults are supervisor choices"}
}
```

For a one-shot assessment use `interval_seconds: null` and an explicit
`next_run_at` (epoch or ISO timestamp with timezone). `schedule_mode: "utc-aligned"`
aligns subsequent periodic runs to UTC interval boundaries. Omitted or null
`limits.max_checks` means no count cap. An explicit positive integer caps lifetime
executions; existing stored integers remain in force. To remove a cap, use
`task-update` with null and the complete limits object, preserving other bounds
and provenance; resume separately if blocked or paused. Other defaults are
a 180-second assessment health checkpoint, 10 seconds per transport call and one
definitely-undelivered recovery after 60 seconds. Overrides retain their source
in `limits.parameter_provenance`. Changing a limit requires actual authority or
an explicit reassessment of a supervisor-owned estimate. The legacy field
`assessment_timeout_seconds` sets that checkpoint, not a worker deadline. Expiry
flags health without revoking reads, interventions or result submission; the task
stays active and no duplicate assessment is sent. A transport timeout means an
incomplete observation or uncertain delivery; reconcile before retrying. Only
explicit operator limits authorize a count/time stop, retaining unfinished work.

Development tasks add `harness: {"repo": "/absolute/worktree", "git_dir":
"/exact/git/directory", "task_id": "existing-completion-id"}`. Keep brief and plan
references in scoped memory; the repository remains their source of truth.

## Assessment

- `execution-read --id UUID`: read-only task, binding and current scoped memory.
- `execution-reconcile --id UUID`: recheck uncertain delivery using the same
  event and current binding generation; never sends. A Claude supervisor awakened
  before confirmation runs this before protected reads/results. If still uncertain,
  preserve the diagnostic and wait for actual delivery evidence.
- `intervention-reconcile --id EVENT_UUID`: explicitly revisit an uncertain
  intervention after new evidence, without another send. Both reconciliation
  commands reject paused, detached or stale authority; old audit observations stay.
- `session-read` input: `execution_id`, `generation`, `session_id`, optional
  `cursor` and `sort_direction` (`desc` initially). Read-only descendant access
  requires a native parent chain to a task target. A `reverse_cursor` is used
  with the opposite direction and includes its anchor's updates. At the start of a check, read the newest descending page and retain its
  reverse cursor as a candidate anchor. Then read the ascending delta from the
  previous persisted anchor, following every `next_cursor`. Persist the new
  candidate only after its observations and the full delta have been assessed.
  This includes active-turn updates and avoids skipping arrivals during the
  check. Do not use an old ascending page's reverse cursor as a newest anchor.
  For Claude, root reads also include public worker histories rooted beneath that
  session. Workers are evidence, not direct intervention targets. Follow the returned
  cursor contract; a changed/truncated prefix or incomplete record is a failed read,
  not an empty delta. Workers may be returned in full on subsequent root reads.
- `harness-inspect --id TASK`: existing harness evidence and freshness, without
  initializing a record. Startup knowledge is not inferred from an old receipt.
- `intervene` input: `execution_id`, `generation`, target `session_id`, unique
  UUID `event_id`, `instruction`, `reason`. Repeating the same ID reconciles the
  same message. It never grants permission to resend an ambiguous action.
- `intervention-status --id EVENT_UUID`: retained delivery receipt, including
  after detach. A receipt is not acknowledgement of compliance.
- `execution-result` input: `id` (execution UUID), `generation`, `outcome`
  (`completed`, `failed`, `blocked`), `summary`, `evidence` and `remaining` lists.
  Include observation cursors and assessment details in scoped memory.

## Memory and lifecycle

`memory-add` takes `supervisor_id`, optional `task_id`, `kind`, `content`,
`source` and `evidence`. Kinds: fact, hypothesis, decision, correction,
authorization, failure, intervention, next-action. `memory-supersede` adds
`supersedes` with the previous item ID in the same scope. `memory-query` takes
the same scope, with optional `include_history: true`; current views exclude
superseded items. Persist cursor metadata as a concise JSON object in `content`
with its session ID, cursor, direction and observation time.

`status` shows tasks, executions and health; `status --id TASK` shows its current
revision. `task-update` takes `id`, `revision`, `changes`; changes invalidate old
assessments. `task-state` takes `id`, `revision`, `action`, `reason`:

- `pause`, `resume`, `cancel` update supervision lifecycle.
- `complete` requires nonempty `evidence` and empty `remaining`.
- `fail` or `block` requires `remaining`; `block` also requires `resume_condition`.

`detach` takes binding `id` and `reason`, fencing its work without cancelling
operational sessions. `deactivate` detaches all bindings in this state root and
removes only its owned cron entry. Task and memory history remain. Reattaching
the same binding leaves tasks paused until explicitly resumed.
