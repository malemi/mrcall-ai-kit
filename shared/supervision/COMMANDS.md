# Supervisor operations

Use the installed kit root, not a guessed repository skill path:

```sh
kit_root="${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}"
python3 "$kit_root/supervision/runtime.py" setup
python3 "$kit_root/supervision/runtime.py" run --state-dir /absolute/new/state-root status
```

`setup` prepares the owned Python dependency environment; `run` executes the
CLI there. Pass `--state-dir ABSOLUTE_PATH` after `run`. Use one new state root
per supervision. Operations with JSON input read stdin; use a file or quoted
heredoc, not shell-interpolated text. All commands return JSON. A nonzero exit
is a refusal or a failure, and its `error` names what is missing.

A state root created by an earlier version keeps its schema. On it the reading
commands, `pause`, `cancel`, `complete`, `fail`, `detach`, `deactivate` and the
memory commands work; `activate`, `task-create`, `task-update` and `resume` are
refused and name the remedy, a new state root.

Every message this CLI sends is recorded first in the account ledger,
`${XDG_STATE_HOME:-$HOME/.local/state}/mrcall-ai-kit/ledger/ledger.sqlite3`. A state
root records the ledger path when it is created. `ledger-backfill` adds the
messages earlier state roots and the goal controller sent, so they classify as
kit messages.

## Activation

`activate` takes `{ "id": "team", "session_id": "EXACT_SUPERVISOR_UUID",
"target_ids": ["EXACT_TARGET_UUID"], "runtime": "codex" }` on stdin. Use
`"runtime": "claude"` for a Claude binding. Runtime is part of immutable binding
identity; every target in a binding belongs to that runtime. Use `--dry-run` to
inspect the owned cron entry without enabling it. Native identity and
direct-input capability are checked. Activation twice is idempotent. For Codex
bindings the native application must be running; activation does not start it.
The supervisor's own tool environment must permit access to Codex's local
control socket and the state directory; report that prerequisite, never change
a session's sandbox or approval policy.

`registry-scan` takes `{ "supervisor_id": "team" }`, optionally
`"operator_session_id"` for a root session outside the binding and
`"history_turns": N` to read further back. It reads the sessions with no model
call and returns the registry: every operator message, each with a reference
`op-…`, its session, time and text. `registry` lists it again. A message the
ledger holds, or one that opens with a kit envelope, is a kit message. A message
older than the ledger is of unknown origin. Neither can be cited.

`task-create` input:

```json
{
  "id": "delivery",
  "supervisor_id": "team",
  "mode": "completion",
  "operator_session_id": "EXACT_SESSION_UUID",
  "target_ids": ["EXACT_TARGET_UUID"],
  "instruction": "The result owed, in one or two sentences",
  "scope": "What the work covers",
  "acceptance": [{"text": "The actual user path passes", "owner": "EXACT_TARGET_UUID"}],
  "interval_seconds": 600,
  "limits": {
    "spend": {"unit": "tokens", "target": 20000000, "ceiling": 30000000, "cites": ["op-…"]},
    "deadline_at": {"value": "2026-11-20T18:00:00+00:00", "cites": ["op-…"]},
    "max_checks": {"value": 40, "cites": ["op-…"]}
  },
  "statements": ["op-…"]
}
```

- `mode` is `completion` or `observation`. An observation task is read and
  reported; `intervene` refuses it, and a limit it reaches parks it with no
  stop sent to its targets.
- `operator_session_id` is required: the supervisor, a target, or another root
  session of the same runtime. A park's question is delivered there.
- `acceptance` items get the identifiers `A1`, `A2`, … in the result. In a
  completion task each names its owner among the targets.
- `limits.spend` is required for a completion task; omitted there, it takes
  `default_spend_limit` from the kit configuration when the operator wrote one.
  An observation task has a spend limit only when given one.
  Its unit is `tokens`, `allowance_percent` (share of the account's allowance
  window; refused when no session of the task reports a window, as with Claude
  Code) or `currency`;
  a currency limit also needs `"prices": {"input", "cached_input", "output"}`
  per million tokens, from the operator. `deadline_at` and `max_checks` are
  optional; `max_checks` counts assessments that ended. Every operator limit has `cites`: registry references, or
  `config:<key>` for an entry the operator wrote in `supervision.json` in the
  kit root (`default_spend_limit`, `prices`). An estimate or a time slot an
  agent wrote is not a limit and is refused here.
- `statements` are registry references quoted verbatim in every message.
- `ask_first` changes the fixed ask-first list: `{"add": [{"item", "cites"}],
  "remove": [{"item", "cites"}]}`.
- Technical parameters in `limits`, each with a default: `heartbeat_seconds`
  1800, `delivery_latest_seconds` 1800, `step_bound` 5, `review_timeout_seconds`
  600, `assessment_timeout_seconds` 180, `transport_timeout_seconds` 10,
  `recovery_attempts` 1. `interval_seconds` is the minimum spacing between
  assessments; `null` with `next_run_at` allows one assessment only.

`task-create --dry-run` validates the same input, creates nothing, and returns
the `authority` text exactly as every message will carry it. Show it to the
operator before creating the task. Creation reads each session once: the token
counters then are the spend baseline, and creation is refused when the
supervisor's or a target's counter cannot be read. A target can belong to one
active completion task at a time across all state roots.

Development tasks add `harness: {"repo": "/absolute/worktree", "git_dir":
"/exact/git/directory", "task_id": "existing-completion-id"}`.

### Claude prerequisite and evidence

A Claude binding runs observation and completion tasks on Linux with the
client's peer protocol 1. Use `claude agents --json` for exact live root IDs.
Supervisor and targets must be running interactive sessions with native
messaging available. `CLAUDE_CONFIG_DIR` selects the native registry and
histories; `--claude-path /absolute/claude` selects the executable. Activation
writes the executable into the owned cron command, and the configuration
directory only when the account's environment sets that variable. No daemon,
session, inbound-permission setting or Agent Team is created for you.

- Give the spend limit in `tokens` or `currency`: Claude Code reports no
  allowance window.
- Every send is `uncertain` when made: nothing acknowledges the socket write.
  The receipt becomes `consumed` when the recipient's history holds the message.
  A working target reads a message inside its running turn at the next tool
  boundary; until then the message is in its native queue and a second
  `intervene` is refused. The queue counts text a human typed and messages of
  other sessions, not the session's own task notifications and subagent reports.
- `session-read` returns one page of a session's history, about 20 kB, newest
  first: follow `next_cursor` for older records and `newer_cursor` for what is
  added later. A long text keeps its start and its end and says how much it
  leaves out; `thread.history_path` names the file that holds all of it.
  `workers` lists the eight subagents changed last, each with its file and the
  last words it said, and `workers_omitted` counts the rest.
- A target whose registry status is `shell` is idle with the flag
  `backgroundShell`: no turn runs and a background command of its own still
  does. Close for it with a wait when it waits for that command.
- At a spend ceiling the lead receives a stop message, at rest or working. A
  running turn ends at its next tool boundary; `status` lists it as continuing
  until then.
- A session in bypass-permissions mode holds a kit message for its user's
  approval. Never change permissions or resend to get past it: park with what
  the operator must approve.
- The supervisor session runs in a prompting permission mode and must be able
  to run this CLI without a permission prompt; a wake reaches it only while no
  turn of its own runs.

## Clock

Cron runs `tick` every minute. A tick reads the sessions with no model call and
dispatches an assessment only when what it read calls for judgment: the task
was activated or updated; a target's turn ended; a target began waiting or
became unreachable; an operator message or a message of unknown origin
appeared; a declared step passed its estimate; spend crossed half or the whole
of its target, or stopped being readable; a wait was met or expired; a delivery
stayed unresolved; a park was rejected; an assessment was abandoned; or the
heartbeat period passed with nothing pending. A trigger inside the minimum
spacing waits. Nothing is dispatched while nothing changed.

## Assessment

- `execution-read --id UUID`: the task, binding and scoped memory, and for the
  assessment its `triggers`, its `closing_set`, the `measured` state and the
  `registry`.
- `execution-reconcile --id UUID`: recheck an uncertain wake using the same
  event; never sends.
- `session-read` input: `execution_id`, `generation`, `session_id`, optional
  `cursor` and `sort_direction` (`desc` initially). Read-only descendant access
  requires a native parent chain to a task target. Follow the returned cursor
  contract; a changed or truncated prefix is a failed read, not an empty delta.
- `harness-inspect --id TASK`: existing harness evidence and freshness.
- `intervene` input: `execution_id`, `generation`, target `session_id`, unique
  UUID `event_id`, `instruction`, `reason`. Python reads the target first and
  refuses when its native queue holds any message or cannot be read, when the
  target is waiting or unreachable, and when the target is working and the
  assessment was raised by the heartbeat alone. The message is rendered in
  labeled parts, the token reminder among them; your instruction is the last
  part, labeled as not the operator's. Do not repeat the reminder in it. Repeating the same ID reconciles the same message and never
  resends.
- `intervention-status --id EVENT_UUID`: the receipt. `queued` until Python
  finds the message in the target's history, then `consumed` with the turn;
  `unresolved` when it is in neither queue nor history at its latest time, or
  still queued on a target that is not working. A receipt is not compliance.
- `intervention-reconcile --id EVENT_UUID`: revisit an uncertain intervention
  without another send.
- `notice` input: `task_id`, `session_id`, `text`, optional `event_id`. One
  rendered notice per task and session, to a session of the binding or to the
  task's operator session; a second one is refused, and so is a notice to a
  target of an observation task. Use it for the end notice; no other channel
  reaches a session.
- `observe --id TASK`: read the task's sessions now and return its status.

`execution-result` input for a completion task:

```json
{
  "id": "EXECUTION_UUID", "generation": 1, "outcome": "completed",
  "summary": "What was assessed and decided", "evidence": ["reference"], "remaining": ["obligation"],
  "items": [{"id": "A1", "status": "open"}, {"id": "A2", "status": "closed", "evidence": ["reference"]}],
  "steps": [{"session_id": "TARGET_UUID", "description": "The step the lead is on",
             "artifact": "/absolute/file/that/will/show/it/done", "estimate_seconds": 900}],
  "steps_closed": ["S1"],
  "closing": [{"session_id": "TARGET_UUID", "kind": "intervention", "event_id": "EVENT_UUID"}]
}
```

- `items` marks every acceptance item. A closed item needs evidence.
- `steps` names, for each target that owns an open item, the step it is on. A
  new step is numbered `S1`, `S2`, …; name a step that continues by its `id`.
  `steps_closed` closes a step only when an earlier assessment declared it and
  its artifact was modified after the declaration; the result says which steps
  stayed open and why.
- `closing` has one entry for each target of the closing set: an
  `intervention` naming an event sent in this assessment, or a wait:
  `{"session_id", "kind": "wait", "condition": {"kind": "time", "at": TIME} |
  {"kind": "file", "path": "/absolute"} | {"kind": "process", "pid": N},
  "latest_at": TIME}`. A waiting or unreachable target accepts only a wait.
- Outcome `blocked` is a park and needs `"park": {"reason", "questions":
  [{"matter", "options": ["…", "…"], "recommendation"}], "completed", "cites"}`.
  The reasons are `ask-first` (with `"item"`, the ask-first entry),
  `operator-restriction` (with registry citations), `operator-input`,
  `limit-reached`, `closure-bounds` and `delivery-unresolved`; Python checks the
  last three against its records. The task is `blocked` when the result is
  recorded.
- After two results in a row that close nothing while no item-owning target was
  working, only a park or a conclusion is accepted; a wait is refused then. A result that leaves every
  item closed is refused: conclude with `task-state complete`.

An observation task takes `id`, `generation`, `outcome`, `summary`, `evidence`
and `remaining`; its outcome `blocked` also needs a `park`.

## Park and question

A park for `ask-first`, `operator-restriction`, `operator-input` or
`closure-bounds` is read a second time, in a fresh context that Python launches
and that holds none of your history, before it takes effect. If that reading
rejects it, the next assessment carries `park-rejected` with the action it
named, and that one intervention is accepted whatever the counts. A second
rejection parks the task with both positions. When a park takes effect, Python
delivers the questions once to the operator session and the task dispatches
nothing. An operator message in an observed session makes it active again for
one assessment that receives it. No command records a verdict or answers a
question for the operator.

## Memory and lifecycle

`memory-add` takes `supervisor_id`, optional `task_id`, `kind`, `content`,
`source` and `evidence`. Kinds: fact, hypothesis, decision, correction,
authorization, failure, intervention, next-action. A `decision` takes `what`,
`why` and `undo` instead of `content`. `memory-supersede` adds `supersedes` with
the previous item ID in the same scope. `memory-query` takes the same scope,
with optional `include_history: true`.

`status` shows tasks, executions and health. `status --id TASK` adds
`measured`: items, steps, both counts, each session's state, running turn, last
turn and queue, deliveries, spend against the limit, parks with their questions
and both positions, pending triggers and waits, reviews, interrupted or
continuing turns, and the recorded decisions. It is read from the state root
alone.

`task-update` takes `id`, `revision`, `changes`; changes invalidate old
assessments. A changed limit needs citations like a new one. `task-state` takes
`id`, `revision`, `action`, `reason`:

- `pause`, `resume`, `cancel` update supervision lifecycle. A parked task
  resumes when the operator writes in an observed session; `resume` on it is
  accepted only with `cites` naming an operator message newer than the park.
  Pausing a parked task keeps the park.
- `complete` requires nonempty `evidence`, empty `remaining` and, for a
  completion task, every item closed; pass `items` to close them.
- `fail` requires `remaining`. `block` requires `remaining` and a `park`.

`detach` takes binding `id` and `reason`, fencing its work without cancelling
operational sessions. `deactivate` detaches all bindings in this state root and
removes only its owned cron entry. Task and memory history remain. Reattaching
the same binding leaves tasks paused until explicitly resumed.

## Protected goal control

This separate API is available only after explicit administrative setup described
in the repository's `docs/supervision.md`, “Persistent goals”. It does not use
`runtime.py`, cron, supervision tasks or assessment execution IDs. Request size is
64 KiB. Client response limit is 4 MiB; keep reports concise and retain large
artifacts by reference. Responses contain `ok` and either `result` or `error`.
In default local mode the existing account can issue all control operations.
Operator instructions reserve administrative operations; peer credentials do not
distinguish a human from an agent in that account. Optional protected mode permits
only root to administer goals and its agent UID to inspect/report/request a check.

```sh
goal_root="$HOME/.local/state/mrcall-ai-kit/goals"
python3 "$goal_root/code/goal_client.py" --socket "$goal_root/control.sock" request \
  '{"op":"inspect","id":"delivery"}'
python3 "$goal_root/code/goal_client.py" --socket "$goal_root/control.sock" request \
  '{"op":"report","id":"delivery","generation":1,"report":{"remaining":"Implement reviewed correction","evidence":["/absolute/trace.json"]}}'
python3 "$goal_root/code/goal_client.py" --socket "$goal_root/control.sock" request \
  '{"op":"check_request","id":"delivery","generation":1}'
```

Read the current generation from inspect; never reuse the illustrative `1` after
operator control changes. An `AI_KIT_GOAL_EVENT` contains `goal_id`, `generation`,
`role`, `socket` and `client`. Inspect restores the goal, reports, last receipt,
last observation and outbox. A stale or non-open event grants no new work.

Consumed lead delivery observations include public activity classification when
available. After failed acceptance, a `no_work` observation causes a corrective
lead prompt through the same outbox; its pending delivery must be reconciled
before another contact. `unknown` does not establish inactivity. Neither a
report nor an execution signal establishes acceptance or new operator authority.

Create request structure (replace paths, UUIDs and hash with reviewed real inputs):

```json
{
  "op": "create",
  "goal": {
    "id": "delivery", "intent": "Deliver the approved behavior",
    "scope": "Exact authorized work, release and spending boundaries",
    "target": {"runtime": "codex", "lead_id": "EXACT_LEAD_UUID", "supervisor_id": "EXACT_SUPERVISOR_UUID"},
    "acceptance": {
      "version": 1, "candidate_root": "/absolute/candidate-inputs",
      "candidate_argv": ["/usr/bin/python3", "-I", "{candidate}/main.py"],
      "checker_root": "/absolute/reviewed-checker",
      "checker_manifest": {"check.py": "SHA256_OF_CHECK_PY"},
      "checker_argv": ["/usr/bin/python3", "-I", "{checker}/check.py", "{result}", "{candidate}"],
      "timeout_seconds": 120
    },
    "limits": {"process_timeout_seconds": 120, "max_wakeups": 20}
  }
}
```

Save the request as a JSON file, then from an operator-authorized shell (local mode needs no sudo):

```sh
/usr/bin/python3 -I "$goal_root/code/goal_client.py" \
  --socket "$goal_root/control.sock" request "$(cat /absolute/goal-request.json)"
/usr/bin/python3 -I "$goal_root/code/goal_client.py" \
  --socket "$goal_root/control.sock" request '{"op":"stop","id":"delivery","generation":1}'
/usr/bin/python3 -I "$goal_root/code/goal_client.py" \
  --socket "$goal_root/control.sock" request '{"op":"resume","id":"delivery","generation":2}'
```

The JSON file is data, never shell code. `create` requires distinct canonical
native root UUIDs; sessions cannot belong to two open goals. Checker manifest
covers the entire bundle. Trees accept regular files/directories only, with
10,000 files, 64 MiB per file and 256 MiB total bounds; select the actual required
inputs instead of an unbounded checkout. Candidate/checker executables are pinned.
Optional acceptance `env` adds operator-bound candidate environment values to
minimal PATH/HOME/locale defaults; local overrides apply to same-account children. Protected mode applies them
after dropping privileges, never to its root launcher. The verifier receives the minimal defaults. `{candidate}`, `{checker}`, `{result}`
and `{scratch}` expand to retained immutable input/output or writable scratch paths.
The checker reads captured candidate-result JSON (`stdout`, `stderr`, `exit_code`,
`termination`) and emits only `{"passed": true}` or `{"passed": false}`.
It judges data; do not execute candidate modules as the verifier.

Operator `set_limits` takes `id`, current `generation` and the complete `limits`
object; it fences in-flight work but does not automatically resume stopped goals.
Supported optional limits are nonnegative `max_wakeups` and timezone-aware ISO
`deadline_at`; omit them for no such cap. `process_timeout_seconds` is required
(positive, at most 3600). Reservations include both session roles and survive
stop/resume. Monetary/subscription budgets are unsupported, not inferred from scope.
Operator `{"op":"tick"}` advances immediately; normally the service clock handles
this. For a long manual tick use client `--timeout` (up to 7200 seconds). A client
timeout is an uncertain response, not proof the operation was cancelled; inspect
before repeating control. The actual process limit is separate from client timeout.

The receipt names `id`, `attempt_id`, generation, acceptance and
candidate/checker identities and captured results. Controller evidence lives under
`evidence/<receipt-id>.json`; retained inputs/output are under `runs/<receipt-id>`.
Agent progress is not a receipt. No API lets an agent force completion or replace
the checker. The reviewed checker remains essential; local mode does not enforce a privilege
boundary against agents in the same account.
