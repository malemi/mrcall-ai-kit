# Persistent session supervision

The `supervision` feature connects a dedicated Codex or Claude Code supervisor to
explicitly authorized root sessions and drives them to verified completion while
the operator is elsewhere. Python observes the sessions, keeps the clock,
measures progress and spend, renders and records every message, and refuses what
its records do not support. A model is called to judge. OpenCode supervision is
not supported; OpenCode `orchestration` is a separate feature. For Python-owned
continuation with executable acceptance, see [persistent goals](#persistent-goals).

## Install and activate

```sh
./install.sh --environment codex --features supervision --mode copy --on-exist backup --yes
```

Installation is dormant: no cron entry, native session, model turn or dependency
download. Refresh skill discovery, then ask for `$supervisor` and identify the
sessions and the intended result. The skill scans the operator's messages into a
registry, builds the task from them, shows the authority text exactly as Python
renders it, the operator session and the identities, and creates the task.
`supervision/POLICY.md` holds what the supervisor judges and
`supervision/COMMANDS.md` every command, under
`${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}`.

```sh
kit_root="${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}"
python3 "$kit_root/supervision/runtime.py" setup
python3 "$kit_root/supervision/runtime.py" run --state-dir /absolute/state-root status
```

Setup owns a private virtual environment with `websockets==16.1`. Python with
venv/pip and user crontab are prerequisites. Codex bindings require a running
Codex app-server and a supervisor whose tools can reach its local control socket
and the state directory. The kit diagnoses failure; it does not alter sandbox or
approval policy, start the daemon or restart sessions.

An operator-written `supervision.json` in the kit root can hold
`default_spend_limit` and `prices`. No command writes it. A completion task
created without a spend limit takes the default and cites it as
`config:default_spend_limit`.

## What Python enforces

**Observation.** Every minute the tick reads, with no model call, the supervisor,
the targets and the task's operator session: status, running and last turn,
native queue, new user messages, the cumulative token counter and the allowance
window. It stores what it reads; a value it cannot read is unknown, never zero.
A target is working with status `active` and no waiting flag, idle with `idle`,
waiting with `active` and a waiting flag, unreachable with `notLoaded` or
`systemError`, unknown when unreadable. `status --id TASK` reports a task from
these records alone.

**Origin of messages.** Every message the kit sends is recorded first in one
ledger for the account; a send the ledger cannot record is not made. A user
message is a kit message when the ledger holds it or it opens with a kit
envelope, inter-agent where the runtime marks it, of unknown origin when it is
older than the ledger, and the operator's otherwise. Only operator messages enter
the registry, and only registry entries or operator-written configuration entries
can be cited. This is provenance for well-behaved runs, not authentication. A
target belongs to one active completion task across all state roots.

**Clock.** An assessment is dispatched only when an observation calls for
judgment: activation or update, a target's turn ending, a target starting to
wait or becoming unreachable, an operator or unknown message, a step passing its
estimate, a spend threshold, unreadable spend, a wait met or expired, an
unresolved delivery, a rejected park, an abandoned assessment, or a heartbeat
with nothing pending. The task interval is the minimum spacing. An assessment
the supervisor never closes is closed as abandoned; two in a row park the task.

**Closing an assessment.** Each result marks every acceptance item and names
each lead's step, its artifact and its estimate. For each target that owns an
open item and is idle with an empty queue, waiting or unreachable, the result
holds an intervention sent and accepted in that assessment, a wait on a time, a
file or a process exit with a latest time, a park, or the task is concluded; a
waiting or unreachable target accepts only a wait. A step closes only when an
earlier assessment declared it and its artifact is newer; declared again in the
same words, it keeps its clock. A closure counts once. After two results that
close nothing while no item-owning target was working, only a park or a
conclusion is accepted, whatever wait the next result offers. Steps that close
while no item closes lead to a convergence review and, the second time, to a
park. An observation task is outside these rules and receives no intervention.

**Receipts.** A kit message is queued until Python finds it in the target's
history, then consumed with its turn. `intervene` is refused while the target's
native queue holds any message or cannot be read, for a waiting or unreachable
target, and for a working target when only the heartbeat raised the assessment.
A message in neither queue nor history at its latest time, or still queued on a
target that is not working, is unresolved. Nothing is resent.

**Authority.** The ask-first list is fixed in code: spending, installation, real
runs against providers, sends to customers, push and release, deleting someone
else's work. A task changes it only with a citation. Operator limits are data —
a deadline, an assessment count, a spend limit — each with citations; a
completion task without a spend limit is refused. Every wake, intervention,
notice and question is rendered in labeled parts: the result owed, the ask-first
list, the limits with the measured spend, the cited operator statements verbatim,
the sentence that everything else is the agents' to decide, the token reminder
the operator asked for, and the sender's text labeled as not the operator's. The
question delivered to the operator session carries no reminder.

**Park and the operator's question.** A park is the task state `blocked` with a
decision request and one of six reasons: an ask-first action, a cited operator
restriction, an input only the operator holds, a limit reached, the closure
bounds, an unresolved delivery. Python checks the last three itself. Before a
park for the first three or for the closure bounds takes effect, Python launches
a fresh-context run that holds the request, the registry, the authority data and
the measured facts, and reads its verdict from that run's own file. A rejection
returns the task with the action the run named; a second rejection, or an
unavailable run, lets the park take effect. Python then delivers the questions
once to the operator session. A parked task dispatches nothing and no timer acts
on silence. An operator message in an observed session makes it active for one
assessment.

**Limits and spend.** Spend is the change in each cumulative counter since the
task was created, summed over the supervisor, the targets and their workers, in
tokens, as a share of the allowance window, or in currency with the operator's
prices. When a counter cannot be read, spend is reported unknown and what was
read is its lower bound. A deadline, a count or a spend ceiling reached parks
the task from the tick. At a spend ceiling of a completion task Python also
interrupts each target's running turn and `status` reports a turn that
continues. Workers are not interrupted, and the targets of an observation task
receive nothing. A convergence review, launched like the challenge, runs when a
step passes twice its estimate, when spend or time since the last item closure
reaches half the target or the time allowed, when spend reaches the target, and
at the step bound. Its result is an intervention to the lead or, when the cut
touches the acceptance or the ask-first list, a park with its second reading.

## What a model judges

Nothing checks these, and the native trial measures them:

- whether the reason of an operator-decision park is true;
- whether a cited statement supports the claimed restriction, and whether an
  authorized action avoids the operator;
- whether a closure is real progress;
- whether the task still states what the operator last asked for;
- whether the lead's path converges, and what to tell the lead;
- whether the session that receives a question presents it and waits;
- whether the supervisor keeps to the CLI: a message sent to a session by other
  means reads as the operator's.

## State and recovery

Each supervision uses its own state root, a private directory with a SQLite
database, selected with `--state-dir`. A state root records the ledger path when
it is created; the ledger is
`${XDG_STATE_HOME:-$HOME/.local/state}/mrcall-ai-kit/ledger/ledger.sqlite3`.
`ledger-backfill` adds the messages of earlier state roots and of the goal
store. Tasks, executions, deliveries, registry, counts, parks, append-only audit
and scoped memory survive restarts and a rotated or lost native history.

A state root created before schema 2 is never migrated. Reading commands, pause,
cancel, complete, fail, detach, deactivate and memory work on it; activation,
task creation, update and resume are refused and name a new state root.

One owned cron block per state root runs `tick` every minute with a minimal
environment and absolute paths. One assessment per supervisor is in flight; a
tick dispatches at most ten. Overlapping ticks skip the held lock. Task edits,
pause, cancellation and detachment fence old executions. An uncertain send is
reconciled against queue and history and never resent. Codex responses have a
64 MiB receive ceiling; a larger frame fails explicitly.

## Claude Code adapter

Install with `--environment claude --features supervision`. A Claude binding
runs observation and completion tasks on Linux. The adapter requires the
client's peer protocol 1 and refuses another number. It is measured on Claude
Code 2.1.296 for sends and 2.1.323 for everything below; a session of another
version is accepted and `metadata` reports it as not measured. The adapter
reads native state and never writes it.

**What it reads.** The live state comes from the session registry, `claude
agents --json` checked against the session's own record: `busy` is working,
`waiting` is waiting with the reason the client names, `idle` is idle, and
`shell`, an idle session whose background command still runs, is idle with the
flag `backgroundShell`. A session that is not listed is unreachable. Queue,
turns, messages and the cumulative token counter come from the session's history
file, read from where the last read ended. The queue holds what a new message
would wait behind: text a human typed and messages of other sessions not read
yet. The session's own task notifications and subagent reports, which the client
can hold while the session rests, are not counted. A model message counts once
however many records repeat it. Workers are the session's subagent files. Only a
message a human typed is an operator candidate. Claude Code reports no allowance
window, so a spend limit in `allowance_percent` is refused.

**How a message travels.** A message is one frame on the session's inbox
socket, opened with the inbox key the session published. Nothing acknowledges
it: the receipt stays uncertain until the recipient's history holds the message.
A session at rest reads it at once as a new turn. A working session keeps it in
its native queue and reads it inside the running turn at the next tool boundary.

**The stop at a spend ceiling.** Claude Code has no call that stops a turn. The
stop is a message with priority `now`, recorded in the ledger as `interrupt`
and rendered like every kit message. It ends the running turn at its next tool
boundary and starts a turn that reads the stop; a tool call in flight runs to
its end first. A lead at rest receives the stop too, so that its own background
work does not start its next turn unaware. `status` shows the stop as
`requested` and lists the turn as continuing while it is still the running one.

**What the client decides.** A session in a prompting permission mode, `auto`
included, accepts a peer message. A session in bypass-permissions mode holds it
for its user's approval, outside the queue the adapter reads, unless that
user's Claude settings accept inbound cross-session messages. The adapter
asserts no mode and changes no setting. A supervisor session needs a prompting
mode in which the kit CLI runs without a permission prompt.

**The fresh-context review.** The run is `claude -p --output-format json
--json-schema … --restricted --no-session-persistence` in the review directory:
no command tools, file tools confined to that directory, no account settings or
hooks, and the verdict returned as structured output.

## Harness

Development tasks link to exact repository/worktree/completion IDs.
`harness-inspect` reuses existing completion semantics and verification warnings
without initializing records or running repository-defined commands. The
repository lead retains orientation, reviews, closure and baseline ownership.

## Stop and remove

On `supervisor end` the skill sends each lead of a completion task one `notice`
through the CLI and stops the supervision without waiting for a reply. `detach` fences one
binding without cancelling its sessions. `deactivate` detaches all bindings of a
state root and removes its cron block. Reattachment leaves tasks paused.

Uninstall runs `deactivate-owned` before removing helpers. It preserves foreign
cron entries, state roots, the ledger and the dependency environment. Modified
helpers or ambiguous owned cron references cause a diagnostic refusal.

## Measured support

Deterministic suites drive the real CLI as a subprocess against a fake Codex
app-server on a Unix WebSocket, with synthetic rollouts and a stub review
command; no model is called. They cover the refusals and Python actions
above: the task contract and citations, origin classes, the ledger, the trigger
clock, the closing rules, receipts, limits and interruption, parks, the
challenge and the convergence review, and the untouched earlier state root.
They establish mechanics, not whether a model judges well.

Codex CLI and app-server 0.169.0 on Linux: the generated protocol schema defines
`turn/interrupt`, `thread/queue/delete` and `thread/items/list`. Passive reads
of two detached sessions through the daemon returned status, queue, turns, every
user message of a turn with its client id and time, and the rollout path; the
`summary` view of a turn holds only its first user message, so messages are read
from the item list. One session's 22 turns and 15 user messages were read in 27
read-only calls and 0.24 seconds, with the counter and allowance window from its
rollout; a second read with the stored cursor returned nothing new in 4 calls.

`tests/supervision_replay.py` drives the same code with the state the retained
records of three runs show at past moments; it reads them locally, read-only,
and prints derived counts. For the 269 recorded assessments of 2026-11-10/11 it
finds a trigger at ten and none inside the two runs of repeated blocked results;
the 136 recorded `blocked` results are refused as parks without a request; every
recorded send to the lead is refused because its native queue held a message;
the 23 messages the lead received are classified as kit messages by the ledger.
For 2026-11-13 at 15:25 UTC it measures 68,202,352 tokens since task creation,
equal to the sum computed from the rollouts alone, and a 30,000,000-token
ceiling parks the task at 14:09:45 UTC with one interrupt call. For the 2026-10-30
goal, with 996 recorded wakes, the third assessment without closure is refused.

Claude Code 2.1.323 on Linux: two suites drive the adapter and the real CLI
against a fake registry, sockets and histories shaped as that version writes
them. They cover the state mapping, the queue with held notifications, turns
ended by the history and by the registry, the counter, workers, the inbox key,
the stop for a running and for a resting lead, an observation task at its
ceiling, and a completion task from wake to ceiling. Replayed record by record,
the histories of three working sessions show a queued message for 243, 77 and
214 seconds in all, one at a time, and none left at the end. On a disposable
live session a message sent at rest started a turn and was found in the history
with its event id; a message sent during a running command stayed queued for 21
seconds and was read inside the turn when the command ended; a stop sent 12
seconds into a 25-second command ended the turn 14 seconds after the send, when
the command ended, and the next turn read it. One fresh-context review run
returned a valid verdict in 10 seconds and 36,621 tokens.

Unverified: `turn/interrupt` on a live Codex turn; a send to a `notLoaded`
thread; a fresh-context run launched by cron, through `codex exec` or `claude
-p`; a Claude session that holds a kit message in bypass-permissions mode;
whether a receiving session presents a question and waits; every judgment listed
under "What a model judges".

## Persistent goals

Persistent goals use a Python service under the **same existing account** as the
Codex sessions. No sudo, additional Linux users or session migration is required.
Every 180 seconds by default it observes exact lead/supervisor identities, checks
acceptance when both are idle and no delivery is pending, and wakes idle sessions
whose goal remains open. A completed lead turn triggers another acceptance check;
a supervisor may request one explicitly. Busy or unknown activity is not interrupted.
Agent reports, including `blocked`, `failed` and `completed`, never close a goal.
Only verified acceptance, explicit stop or an operator limit ends admission.
Delivery uncertainty is reconciled against the exact event's native history;
it is never blindly resent.

### Automatic intervention after inactivity

After a consumed lead wake, the controller classifies structured public events
in that turn and newer turns. A completed turn containing only messages and
recognized goal bookkeeping is `no_work`. Executed commands, file changes and
work tools are execution signals, not proof of useful progress. The narrow
bookkeeping recognizer accepts goal-client control calls and supported Python
report wrappers; arbitrary or mixed commands count as execution. Active work
defers intervention. Incomplete or unfamiliar event data remains `unknown`.

When acceptance is still negative and the consumed lead wake has `no_work`,
Python sends a corrective prompt directly to the lead through the durable
outbox. It requires a concrete authorized next action or a precise action,
constraint and decision needed from the operator. Agent reports alone cannot
suppress that prompt. It carries the existing scope and spending restrictions,
does not authorize failed-operation retries, and does not certify a blocker.

The observation and corrective delivery are inspectable with the goal. Pending
or uncertain delivery prevents another send; reconciliation survives restart
and operator generation changes. Continued inactivity after a consumed corrective
turn can produce another correction on the next eligible cycle. This detector
does not judge experiment quality, guarantee model compliance, or apply to
supervision tasks. Unknown observations retain the ordinary wake path
without claiming that absence of work was established.

Ordinary supervision installation supplies dormant assets. Default setup uses the
current UID, GID and HOME for controller, native bridge, candidate and checker:

```sh
kit_root="${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}"
goal_root="$HOME/.local/state/mrcall-ai-kit/goals"
python3 -I "$kit_root/supervision/goal_setup.py" --root "$goal_root" \
  --websockets-source /absolute/websockets --cadence-seconds 180 \
  --native-socket /absolute/codex.sock --codex-path /absolute/codex
python3 -I "$goal_root/code/goal_service.py" --config "$goal_root/config.json"
```

The root path must be new and its parent must exist. Setup copies the runtime and
`websockets==16.1` without downloading dependencies or starting a service.
Native sessions keep their existing identity and account. Use a user service or
another explicitly configured process manager to keep the controller running.
A local-mode setup records the account ledger path in its configuration, and the
driver records each wake there before sending it; a send the ledger cannot record
is not made. A protected-mode service has no ledger path and its messages classify
as kit messages by their envelope. A goal service set up before the ledger existed
runs its own copy of the code and records nothing until it is set up again.
Local children have bounded runtime/output and process-group cleanup; detached
processes are outside that cleanup guarantee. No privileged namespaces are needed.
Same-account peers can issue control commands: distinguishing a human from an
agent with identical privileges is not a security claim. Agent instructions
reserve stop, limits and acceptance changes for the operator.

The optional `--mode protected` deployment retains root-owned runtime/state,
distinct non-root agent/verifier UID/GID/home options and Linux PID/mount namespaces.
It requires root and CAP_SYS_ADMIN. Its shipped `goal.service` is a root systemd
template for `/var/lib/mrcall-ai-kit-goals`, not a requirement for local mode.
Existing configuration without `mode` retains protected behavior. Protected mode
still cannot protect an agent account with unrestricted sudo. Neither setup mode
creates users or changes privilege policy. Claude/OpenCode goal targets remain
unsupported.

The client's JSON operations and complete goal contract are in
[COMMANDS.md](../shared/supervision/COMMANDS.md#protected-goal-control).
`verify` prepares executable acceptance from the approved brief; `reviewer`
reviews its meaning and failure cases before the operator binds it. `debugger`
is needed only when a failure's cause requires investigation. The candidate runs
from a retained read-only snapshot. A separately pinned Python
checker runs under the configured checker UID, judges captured output/data, and must emit exactly
`{"passed": true}` with exit zero. Candidate execution must also exit zero without
termination. A malformed checker, changed source, tampering or timeout keeps the
goal open. Receipts identify the actual snapshot and checker hashes; their acceptance
digest links to executable hashes in the bound goal contract.
The checker must not import or execute candidate code with verifier privileges.
Acceptance quality still depends on the reviewed test; the service cannot prove
arbitrary intent. Bind repeatable, in-scope commands and declared inputs/dependencies;
external side effects and resources need their own authorization and accounting.

Supported limits are `deadline_at`, `max_wakeups` and required
`process_timeout_seconds`. There is no default failure/wakeup cap. Wake allowance
counts durable reservations for both sessions, including a refused/uncertain send;
it is not a token or dollar counter. The last admitted turn may finish and pass
acceptance before wake exhaustion closes admission. Unknown fields, including
unsupported money/subscription budgets, are rejected. Scope prose is not budget
enforcement. Stop fences new launches and late completion; it does not cancel a
native model turn already admitted. Resume preserves pending delivery and counters.
Direct resume of a completed goal is refused; changed intent/acceptance needs a
new goal.

For rollback, stop each goal through the client, stop the service and retain
its protected database, checker bundles, run artifacts and evidence. Restart uses
the same state; do not reset uncertain events or consumed allowance. Per-user
uninstall removes dormant assets but does not remove a separately provisioned
goal installation or stop its service. Supervision deactivate/detach cannot stop goals.

Independent isolated CLI/socket tests exercise failed acceptance, actual wake
frames, corrected-candidate completion, restart/delivery races and OS-principal
separation. A native protocol fixture avoids paid models and live session changes;
these checks do not establish model judgment or production deployment. Evidence
and review references are in the [goal plan](execution-plans/2026-10-30-persistent-goal-driver.md).

Local-mode evidence and deployment scope are recorded in the
[local controller plan](execution-plans/2026-10-30-local-goal-controller.md).
Normal-account installed checks cover failed acceptance, both idle wakes,
restart reconciliation and corrected completion, plus child timeout/output
bounds. Protected-mode security evidence remains separate from these local
checks; neither establishes general model judgment.
