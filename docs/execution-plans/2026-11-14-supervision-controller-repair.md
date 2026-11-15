---
status: active
created: 2026-11-14
brief: ../briefs/2026-11-13-supervision-controller-repair.md
---

# Supervision controller repair

The [brief](../briefs/2026-11-13-supervision-controller-repair.md) is APPROVED by
the `reviewer` agent on its third pass. The lead is Claude Code session
`2c135815-d75a-450a-b4e2-c2f206c2e8e7`; its
[session memory](../sessions/2c135815-d75a-450a-b4e2-c2f206c2e8e7.md) holds the
verified evidence beyond the brief.

## Authorization

The operator's messages of 2026-11-14 08:50 and 08:53 UTC mandate finishing and
installing the repair, give it the highest priority and allow interrupting
whatever runs. Installing the `supervision` feature into the kit home is
authorized. The operator's messages of 2026-11-15 16:13 UTC authorize a default
spend limit chosen by the lead, stopping the goal service, the native trial on
the Claude Code sessions PROBLEMI6 and REMOTE, and a commit and push of the
working tree. Not authorized: a release, and deleting the goal controller's code.

## Decisions taken without the operator

The brief left four decisions to the operator. The lead took each as follows;
the delivery reports each with its undo.

- **Required spend limit.** A completion task without one is refused; an
  operator-written kit configuration entry can supply the default. Undo: one
  validation in `store.py`. On the operator's delegation of 2026-11-15 the
  account default is 60,000,000 tokens as target and 120,000,000 as ceiling, in
  `supervision.json` of the kit home. The 2026-11-13 run spent 68 million tokens
  in two and a half hours. The counter of the Claude lead PROBLEMI6 rose by 221
  million between 2026-11-13 15:46 and 2026-11-15 16:14 UTC, and its workers
  spent 102 million in the day before 2026-11-15 17:05 UTC.
- **Goal controller.** Its code stays. Its deployed service is stopped and
  disabled by the operator's decision of 2026-11-15. The repository's goal
  driver records its sends when its configuration names a ledger.
- **Token reminder.** Kept, by the operator's decision of 2026-11-15: it is a
  labeled part of every rendered message to an entrusted session, beside the
  cited spend limit and the measured spend; the question for the operator
  carries none. The token-reminder plan stays active.
- **Base.** Milestones M1 to M3 are commit `54007b0` on the pushed branch
  `supervision-controller-repair`, beside three commits of earlier work.

## Measured before design

Codex 0.169.0, from the generated protocol schema and passive reads of two
detached kit sessions on 2026-11-14; the session memory holds the details.

- The protocol defines `turn/interrupt`, `turn/steer`, `thread/queue/delete`
  and `account/rateLimits/read`; their live behavior is unverified. Nothing
  shows the operator content without a turn.
- A thread status is `idle`, `active` (flags `waitingOnApproval`,
  `waitingOnUserInput`), `notLoaded` or `systemError`. `thread/read` returns it
  with the rollout `path`. A thread no client holds is `notLoaded`.
- The `summary` view of `thread/turns/list` holds only a turn's first user
  message. `thread/items/list` with a `turnId` returned every item with its
  `startedAtMs`, honors the anchor `{"type": "item", "itemId": …}` and
  `deferOutput`, and refuses an unknown anchor with code -32602. Items include
  `reasoning`, which is never stored.
- Rollouts hold cumulative `thread_token_usage`, `rate_limits`, and a header in
  which a worker names the root's `session_id`.
- Root user messages carry provenance `user` whoever sent them; no field marks
  a message between root sessions.
- Claude Code here is 2.1.323. Each live session publishes a registry record
  with its status, a peer protocol number and an inbox socket, and writes a
  history file with its turns, its queue operations, the origin of every
  message and the token usage of every model message. `supervision.md` holds
  what the adapter reads from them.

## Design

### Account ledger

`shared/supervision/ledger.py` owns one private SQLite file for the account,
`${XDG_STATE_HOME:-$HOME/.local/state}/mrcall-ai-kit/ledger/ledger.sqlite3`. A state
root records the ledger path when it is created, from
`MRCALL_SUPERVISION_LEDGER` or that default, and every later command and tick on
that root uses the recorded path. Every suite sets the variable to a temporary
file before it creates a root.

- `messages`: one row per kit send — client message id, session, kind (`wake`,
  `intervention`, `question`, `notice`, `review`, `goal`, `backfill`), state
  root, task. A send is recorded before it is attempted, and a send whose
  record cannot be written is refused.
- `claims`: the completion task that holds each target. Creating or resuming a
  completion task claims its targets. A claim is released on pause, detach and
  terminal states, and is ignored when its state root is gone or its task is no
  longer active or parked there. A live claim by another task refuses.
- `meta`: the epoch, the moment the ledger was created.
- `backfill` reads, read-only, the outbox and intervention identities of every
  sibling state root and of the goal store.

`goal_setup.py` copies `ledger.py` and writes the ledger path into a local-mode
configuration; the goal driver records each send there first. A protected-mode
service has no ledger path, sends as today, and its messages classify as kit by
their envelope.

### Observation

Each transport gains `observe(session_id, cursor, workers_since)`. It returns
status, native queue, new and still-open turns, their user messages with times,
the cumulative token counter, the allowance window, the session's workers with
their counters, a new cursor, and the names of the values it could not read.
The Codex transport also gains `interrupt`.

The Codex adapter reads status and path from `thread/read`, the queue from
`thread/queue/list`, turn boundaries from `thread/turns/list` without items,
and user messages from `thread/items/list` with deferred outputs, anchored on
the last item stored. A message's time is its item's `startedAtMs`, else its
turn's start. Counters and allowance come from the rollout, read forward from a
stored offset. Workers are the rollouts whose header names the root's
`session_id`, searched from the day before `workers_since`.

`shared/supervision/observe.py` runs at each tick for every task that is active
or parked. It observes the supervisor, the targets and the operator session,
writes what it reads, and returns triggers. Schema version 2 has these tables
besides the present ones:

- `sessions`: latest snapshot per session, its cursor and its unknown values. A
  failed read keeps the last known values and marks them stale.
- `observations`: append-only facts — turn started, turn ended, status, queue,
  counter, allowance, read failure.
- `messages`: append-only, every user message read, with its origin. An
  operator message gets the reference `op-` plus ten hex digits of the SHA-256
  of session and item identity. The registry is the rows with origin `operator`.
- `deliveries`: one row per message this root sent, wakes included: `queued`
  from the send until its client id appears in `messages`, then `consumed` with
  the turn. At its latest time, counted from the send, a message is
  `unresolved` when it is in neither the native queue nor the history, or still
  sits in the queue of a target that is not working. A message queued behind a
  working target has no deadline.
- `items`, `steps`, `closures`, `waits`, `parks`, `triggers`, `reviews`, `meta`.

Origin, in order: the ledger holds the client id, or the text opens with a kit
envelope marker — kit; the runtime marks another agent as sender — inter-agent;
the time is before the ledger epoch or unreadable — unknown; otherwise operator.

A target is **working** only with status `active` and no waiting flag. It is
**idle** with status `idle`, **waiting** with `active` and a waiting flag,
**unreachable** with `notLoaded` or `systemError`, and **unknown** when its
status is unreadable.

### Task contract

A task in a schema-2 root carries these fields.

- `mode`: `completion` or `observation`.
- `operator_session_id`: required; the supervisor, a target, or another root
  session of the same runtime, verified through the transport at creation.
- `acceptance`: items with text and an owner among the targets. Python assigns
  `A1`, `A2`, … and never renumbers.
- `limits.spend`: required for a completion task; unit `tokens`,
  `allowance_percent` or `currency`; a target, a ceiling and `cites`. A
  currency limit needs `prices` per million input, cached-input and output
  tokens, from the limit or the kit configuration, and is refused without them.
- `limits.deadline_at`, `limits.max_checks`: a value and `cites`.
- `statements`: registry references rendered verbatim in every message.
- `ask_first`: changes to the fixed list, each with `cites`.

A `cites` entry is a registry reference of this root or `config:<key>`, an
entry of `supervision.json` in the kit home, which no command writes. Technical
parameters keep their provenance rules and gain `heartbeat_seconds` (1800),
`delivery_latest_seconds` (1800), `step_bound` (5), `review_timeout_seconds`
(600).

Creation observes the sessions once. The counters of the supervisor, the
targets and the workers found are the spend baseline; creation is refused when
the supervisor's or a target's counter is unreadable. A worker found later
starts from zero when its rollout was created after the task, otherwise from
its first reading. Messages already present are stored and raise no trigger.

### Clock

`Scheduler._claim` creates an execution only for an active schema-2 task with
an undelivered trigger, no open execution for its supervisor, and a previous
execution scheduled at least `interval_seconds` ago. A trigger inside that
spacing stays pending. The execution carries its triggers and its **closing
set**: the targets that own an open item and at that moment are idle with an
empty native queue, waiting, or unreachable. It also records whether any target
that owns an open item was working.

Triggers: `activated`; `task-updated`; `turn-ended` for a target;
`target-waiting` when a target becomes waiting and `target-unreachable` when it
becomes unreachable, each once per transition; `operator-message` and
`unknown-message` in any observed session; `step-overrun` at a step's estimate;
`spend-threshold` at half and at the whole spend target; `spend-unknown` when
spend stops being readable; `wait-met`, `wait-expired`; `delivery-unresolved`
for an intervention; `park-rejected`; `assessment-abandoned`; and `heartbeat`
when no trigger, wait or queued delivery is pending and the last assessment
ended more than `heartbeat_seconds` ago.

An execution past its assessment checkpoint for `heartbeat_seconds` is closed
as `abandoned` and raises its trigger. Two abandoned in a row, or an unresolved
wake, park the task with reason `delivery-unresolved`.

### Closing an assessment

A result on a schema-2 completion task carries, besides the present fields:

- `items`: every acceptance item, `open` or `closed`, with evidence when closed;
- `steps`: for each target that owns an open item, the step it is on, the
  absolute path of the artifact that will show it done, and the lead's estimate
  in seconds; a new step is numbered `S1`, `S2`, …;
- `steps_closed`: step ids. A step closes only if an earlier assessment
  declared it and its artifact was modified after the declaration;
- `closing`: one entry per target of the closing set — an `intervention` naming
  an event this execution sent, recorded `queued` or `consumed`, or a `wait`
  with a condition (`time`, `file`, `process`) and a latest time. A waiting or
  unreachable target accepts only a wait. Outcome `blocked` closes every target
  with a park. A conclusion uses `task-state`.

Validation reports every reason it refuses. A closing-set target without a
valid entry is refused, and the refusal names the four closings. A wait on the
operator is refused with the instruction to park. A result that leaves every
item closed is refused: the task is concluded with `task-state complete`.

A closure counts once per item and once per step. The no-closure count rises by
one for a result that adds no closure and ends in no wait, unless a target that
owns an open item was working when the execution was claimed, and by one when a
wait expires unmet. A closure or an operator message resets it. At two, a
result that would raise it is accepted only with outcome `blocked`. So an
assessment over a working target never counts, and one over targets that are
idle, waiting, unreachable or unknown always does. The step count rises with
each step closure
and resets when an item closes or an operator message arrives; at `step_bound`
Python launches a convergence review, a verdict of shortest path resets the
count, and reaching the bound again parks the task.

An observation task accepts results without these fields.

### Receipts and sends

`intervene` observes the target first. It refuses an observation task, a target
whose native queue holds any message or is unreadable, a waiting or unreachable
target, and a working target when every trigger of the execution is
`heartbeat`. It renders the message, records
it in the ledger and in `deliveries`, then sends. `notice` sends one rendered
notice to a session of the binding and replaces the skills' direct end notice.
Reconciliation never resends.

### Authority

`shared/supervision/authority.py` holds the ask-first list and renders every
wake, intervention, notice, review result and question in labeled parts: the
result owed; the ask-first list; each operator limit with its citations and the
measured spend; each cited statement verbatim with reference, session and time;
the sentence that anything else is the agents' to decide and record with its
undo; and the sender's text under a label saying it is not the operator's.
`memory-add` with kind `decision` requires `what`, `why` and `undo`.

### Park, challenge and the operator's question

Outcome `blocked` and `task-state block` require a `park`: a reason, questions
each with matter, options and recommendation, what else was completed or why
nothing else can proceed, and `cites`. The reasons are `ask-first`,
`operator-restriction`, `operator-input`, `limit-reached`, `closure-bounds` and
`delivery-unresolved`. `operator-restriction` needs registry citations. Python
checks the last three against its records. Any other reason is refused with the
instruction to decide and proceed. One transaction records the park and sets
the task `blocked`.

A park for one of the first three reasons or for `closure-bounds` starts as
`challenging`; the others take effect at once. `shared/supervision/review.py`
launches a fresh-context run as a detached process and reads the verdict from
that process's output file under the state root. Its input holds the decision
request, the registry, the authority data and the measured facts, and nothing
else. The Codex command is `codex exec --ephemeral --skip-git-repo-check
--sandbox read-only --json -C <review directory> --output-schema … -o …`; a
Claude binding uses `claude -p --output-format json --json-schema …
--restricted --no-session-persistence`;
`MRCALL_SUPERVISION_REVIEW_COMMAND` replaces either in tests. No command reads
or writes a verdict. A run that fails, times out or returns a malformed verdict
is unavailable, and the park takes effect.

A challenge answers the brief's three questions and is `uphold` or `reject`
with a named action. Uphold or unavailable makes the park effective. A
rejection returns the task to active with a `park-rejected` trigger, and the
next result may record that one intervention whatever the no-closure count.
Python counts rejections since the last closure or operator message; the second
makes the park effective with both positions in the request.

When a park takes effect Python sends the decision request once to the operator
session, with the instruction to present it and wait. A parked task is observed
and dispatches nothing. An operator message in an observed session sets it
active with one `operator-message` trigger, and limits are not enforced until
that one assessment ends. A park in that assessment whose reason and matters
equal the reactivated park's takes effect with no challenge and no send.

A convergence review is launched the same way when a step passes twice its
estimate, when spend since the last item closure reaches half the spend target,
when the time since the last item closure reaches half the time between
creation and the deadline, when total spend reaches the target, and at the step
bound. Its verdict names the shortest path and what to cut. Python delivers the
intervention to the lead under the review's label once the lead's queue is
empty, and stores it as supervisor memory. A verdict that touches the
operator's acceptance or the ask-first list parks the task with the review's
question and no challenge.

### Limits and spend

Spend is the sum, over the supervisor, the targets and their workers, of the
counter now minus its baseline. An unreadable counter makes spend unknown: it
neither satisfies nor breaks a limit, `status` says so, and `spend-unknown` is
raised. Allowance spend is the change in used percent, carried across a window
reset. Currency spend applies the price table to the input, cached-input and
output deltas.

A deadline, a count or a spend ceiling reached parks the task from the tick
with reason `limit-reached` and a request Python writes from the measured
values. At a spend ceiling Python also calls `interrupt` on each target's
running turn and records the outcome; `status` reports a turn that continues.
Workers are not interrupted.

### Status

`status --id <task>` adds a `measured` object read only from the state root:
items, steps, both counts, each session's status, running turn, last turn,
queue and unknown values, deliveries, spend against the limit, parks with their
questions and both positions, pending triggers and waits, review tokens, and
the `decision` memories.

### Earlier state roots

A schema-1 root is never migrated. On it the commands that read, and `pause`,
`cancel`, `complete`, `fail`, `detach`, `deactivate` and the memory commands,
work as before. `activate`, `task-create`, `task-update` and `resume` refuse it
and name the remedy: a new state root, where the task is created with the
required fields. No tick dispatches a schema-1 task.

## Milestones

Implementation is delegated to `execute` agents with this plan as their
specification. The lead integrates, runs every `tests/test_supervision_*.py`
suite at the end of each milestone, and owns the documents of M2.

**M1 — controller.** `ledger.py`, `observe.py`, `authority.py`; `observe` and
`interrupt` in the Codex transport; schema 2, the contract, results, parks and
`measured` in `store.py`; triggers, limits, abandonment and the question in
`scheduler.py`; `intervene` and `notice` in `control.py`; CLI commands
`observe`, `registry-scan`, `registry`, `notice` and `ledger-backfill`; the
ledger in `goal_driver.py` and `goal_setup.py`; the existing suites moved to
the contract. A park takes effect without a challenge. Depends on nothing.

**M2 — reviews, replays, instructions.** `review.py` with the challenge and the
convergence review; `tests/supervision_replay.py`; `POLICY.md`, `COMMANDS.md`,
both skills, `supervision.md`, the installer's and uninstaller's asset lists,
and `CHANGELOG.md` under `Unreleased`. Depends on M1.

**M3 — installation.** `install.sh --features supervision` for Codex and Claude
in copy mode with backup; then the suites against the installed CLI through
`AI_KIT_SUPERVISION_TEST_CLI`, `ledger-backfill` on the account, and `status`
of an earlier state root. Depends on M2 after its review.

**M4 — Claude sessions.** `observe` and `interrupt` in the Claude transport,
gated on the peer protocol; the stop as a rendered and recorded message in
`scheduler.py`; the refusal of an allowance limit where no session reports a
window; the Claude review command; the two Claude suites; the adapter's
documents and skill. Depends on M3.

A fresh `reviewer` reviews M1 and M2 together before M3 starts. A separate final
review runs through the installed CLI. `doc-end` follows it. The operator asked
on 2026-11-15 for a leaner path; the M1 review was merged into this one. A fresh
`reviewer` reviews M4 with its documents before the native trial starts.

## Verification

Each property is proved by the named observation, read where stated. Tests use
the real CLI as a subprocess and the Unix WebSocket fixture of
`tests/test_supervision_transport.py`, extended with `thread/items/list`,
`turn/interrupt`, a synthetic rollout, and a stub review command that logs each
launch.

| Property | Observation that proves it | Read from |
|---|---|---|
| Observation is read-only | a tick with no trigger calls only `thread/read`, `thread/queue/list`, `thread/turns/list`, `thread/items/list`; the stub log is empty | fixture calls, stub log |
| An unreadable counter is unknown | `measured.spend` names the session as unknown, holds no number, and `spend-unknown` is pending | `status` |
| A restart or lost history keeps records | parks, questions, deliveries, registry and counts equal after reopening against an empty fixture history | `status` |
| Every kit send is in the ledger | one row per accepted `thread/queue/add`, for wake, intervention, notice and question | ledger, fixture calls |
| A failed ledger write refuses the send | no `thread/queue/add`, error naming the ledger | CLI exit, fixture calls |
| The recorded ledger path wins | a tick run without the variable writes the ledger the root recorded | ledger files |
| Origin classes | one message per rule: ledger id, envelope, peer mark, pre-epoch time, none | `registry`, `messages` |
| Only registry entries are cited | a limit or `ask_first` change citing a kit message, or citing nothing, is refused | CLI error |
| One completion task per target | a second task in another root is refused; a claim of a deleted root is ignored | CLI output, `claims` |
| Required fields | a task without `mode`, without `operator_session_id`, with an operator session the transport does not know, or a completion task without a spend limit or with an unreadable baseline, is refused | CLI error |
| No dispatch without a trigger | repeated ticks over unchanged state add no execution | `executions` |
| Each trigger dispatches once | for each trigger kind, one execution whose wake lists it | `executions`, fixture calls |
| Spacing postpones a trigger | no execution inside the interval, one after it | `executions` |
| Heartbeat | none while a wait or a queued delivery is pending; one after the period over a busy target | `executions` |
| The four closings | a result with no entry for a closing-set target is refused and names them; the same result is accepted after the target turned busy from this execution's intervention | CLI output |
| A target that is not working is bounded | a result with no wait for a waiting or an unreachable target is refused, and its wait raises the count when it expires unmet; an unreadable target raises the count on a result without closure or wait; `intervene` to the first two is refused; a result leaving every item closed is refused | CLI output, `measured` |
| A result names items and steps | a result missing an item or a step is refused, and every reason is listed | CLI error |
| A wait on the operator is refused | error naming park | CLI error |
| `blocked` stops the clock | task `blocked`, no later execution | `status`, `executions` |
| An old artifact closes nothing | step open, count unchanged | `measured` |
| A closure counts once | reopen and close leaves the count unchanged | `measured` |
| Two idle results without closure | the third non-park result is refused; results over a working target leave the count at zero | CLI error, `measured` |
| An unmet wait counts | count rises when the wait expires | `measured` |
| An operator message resets counts | counts zero after the tick that reads it | `measured` |
| Step bound | a review launched at the bound; park at the second | stub log, `status` |
| Queue rule | `intervene` refused while `thread/queue/list` returns an entry or fails | CLI error |
| No message because time passed | `intervene` to a working target refused in a heartbeat-only execution | CLI error |
| Delivery lifecycle | `queued`, then `consumed` with its turn; still `queued` past its latest time behind a working target; `unresolved` when it is in neither queue nor history, or queued on an idle target, with its trigger and an accepted `delivery-unresolved` park | `measured`, `executions` |
| Abandoned assessments | one closes as `abandoned` and re-wakes; the second parks the task | `executions`, `status` |
| Observation mode | `intervene` refused; result accepted without closing | CLI output |
| Rendered parts | the accepted input holds the six parts and the cited text verbatim, for a wake and for `notice` | fixture input |
| Decision memory | a `decision` without `undo` is refused | CLI error |
| Park reasons | a seventh reason is refused; a false measured reason is refused | CLI error |
| No verdict command | no CLI command takes a verdict; the review input holds no memory, audit or summary text | parser choices, input file |
| Challenge outcomes | uphold, reject, second reject and unavailable each leave the stated state | `status`, fixture calls |
| One question, no timer | one `thread/queue/add` to the operator session; later ticks add none | fixture calls |
| Operator message reactivates | task active with one trigger; a park with equal matters adds no review and no send; a raised limit recorded in that assessment holds | `status`, stub log |
| Limits park | deadline, count and ceiling each give `blocked`, `limit-reached`, no later execution | `status`, `executions` |
| Ceiling interrupts | one `turn/interrupt` per running target turn; a refused one reports the turn as continuing | fixture calls, `status` |
| Convergence triggers | each of the five launches one review; a cut that touches acceptance parks with no challenge | stub log, `status` |
| A rejected park then a closure continues | task active, counts reset | `status` |
| Earlier root untouched | file bytes equal after `status` and after a refused `task-create` | file hash |
| A Claude session is read without a model call | state from the registry; queue, turns, messages and counter from the history; a second read with the stored cursor returns only what was added; a session that is gone reads `notLoaded` | Claude adapter suite |
| A Claude completion task runs through the CLI | a lead whose client holds a notification is in the closing set; a wake uncertain then delivered; an intervention consumed from the lead's history; a second send refused while the lead's queue holds a message; a ceiling parks the task and sends one stop with priority `now`, to a lead at rest too; `status` lists the turn as continuing while it is the running one | Claude CLI suite |
| A Claude queue holds only unread messages | a held notification or subagent report is not reported; a kit message that starts a turn leaves the queue; an entry on record from before the session came to rest is dropped | Claude adapter suite |
| An allowance limit needs a window | a completion task with `allowance_percent` over sessions that report none is refused | Claude CLI suite |
| An observation task's targets receive nothing | an observation task takes no default limit; at a ceiling it was given it parks, records no stop and sends no frame to its targets | Claude CLI suite |
| The cron entry leaves the client's configuration where it is | no `CLAUDE_CONFIG_DIR` in the entry unless the account sets it; an entry that carries it keeps it | cron suite |
| Fences and uncertain delivery | the existing cases for pause, detach, stale execution and reconcile-once pass | existing suites |

Brief acceptance item 8 is verified by the M2 reviewer and `doc-critic`: every
normative sentence left in `POLICY.md` and the skills is checked against this
table, and none may restate a row.

### Replays

Expected values come from the brief, the session memory and
`spend_expected.py` in the lead's scratchpad. All were computed from the
records without this code.

- **2026-11-10/11.** No trigger for assessments 125 to 150 and 162 to 269. The
  results of 124 and 161 refused for a park without reason and request. Every
  send made while the lead's queue held a message refused, including the five
  of 16:52 to 18:37. 23 lead messages classified kit by the ledger, none by the
  envelope alone, none in the registry.
- **2026-11-13.** At 15:25:00: no item closed; the lead's turn running since
  13:13:54; an intervention queued since 14:29:44; spend 68,202,352 tokens —
  supervisor 10,575,887, lead 40,144,210, nine workers 17,482,255. A ceiling
  below that total parks the task at the crossing. The replay reports its
  triggers against the 14 recorded assessments.
- **2026-10-30 goal.** The no-closure count reaches two at the second consumed
  lead wake followed by a failed check, against 996 recorded wakes.

## Native trial

The trial runs on this machine since 2026-11-15 17:50 UTC.

- State root `~/.local/state/mrcall-ai-kit/supervision-claude-trial-20261115`,
  binding `trial`, runtime `claude`, one owned cron entry.
- Supervisor: a dedicated Claude Code session, `4cd32507-d2b1-4204-a98b-681d24ca4f89`,
  in the tmux session `kit-supervisor`, started in a clean environment with no
  typed prompt. Its mandate reaches it in the controller's wake.
- Targets: PROBLEMI6 `8a1c9706-bec4-4d9d-b8c9-1d6650b2d200` and REMOTE
  `617dd083-145f-41e1-975e-e50096c231f4`. Operator session: the lead's own,
  `2c135815-d75a-450a-b4e2-c2f206c2e8e7`.
- Task `problemi6-closing`: completion, target PROBLEMI6, eight acceptance items
  that restate the operator's closing mandate of 2026-11-15 16:08 UTC, the spend
  limit of the configuration default. The ask-first entries on installing and on
  real runs are removed for this task and cite that message, which orders both.

Observed: the cron tick, in its minimal environment, read the four sessions; the
wake reached the supervisor at rest and was in its history two seconds later; the
supervisor loaded the skill, read the lead through `session-read`, and closed its
first assessment through the CLI with a declared step, in 1 minute 44 seconds and
889,344 tokens of its own.

Not yet observed: an intervention read by the live lead; a park with its
challenge launched from cron and the question in the operator session; a spend
threshold or ceiling with its stop; the conclusion of the task. A task for REMOTE
needs the operator's statement of the result REMOTE owes.

## Rollback

Restore the changed paths from the base archive and delete the added files; the
session memory keeps the list. The installer backs up each replaced asset
beside it. Schema-1 roots are untouched. Schema-2 roots and the ledger are new
state: the earlier code refuses a schema-2 root, and both can be deleted.

## Left for the operator's authorization

A release, and retiring the goal controller's code.

## Recorded limits

- `turn/interrupt`, a send to a `notLoaded` thread, and `codex exec` launched
  from cron rest on the schema, the CLI help and fixtures; their live behavior
  is unverified until the trial.
- `turn/steer` is not used: a message to a busy target waits in the native
  queue for the turn to end.
- A Claude session reports no allowance window: its spend limit is in tokens
  or currency.
- The stop a Claude lead receives ends its turn at the next tool boundary, not
  at once: measured 14 seconds after the send, when the running command ended.
- A Claude session in bypass-permissions mode holds a kit message for its
  user's approval; the adapter asserts no mode. Not exercised live.
- A Claude session records the removal of a queued entry without the entry's
  identity. The adapter matches a kit message by its event and other messages
  by text or kind; a session at rest is read as holding no unread message.
- A turn that the stop ends is recorded as completed, not as interrupted.
- `task-create --dry-run` returns the rendered authority for the display before
  activation, and a question that was definitely not delivered is offered again
  after ten minutes; neither is in the design text above.
- Review tokens are read from the run's output and reported; the spend limit
  does not govern them.
