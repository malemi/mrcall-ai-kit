# Persistent session supervisor

Date: 2026-10-26
Status: proposal for independent brief review and implementation planning; no implementation or release authorized.

## Intent

Let an operator entrust existing AI sessions to a separate supervisor without
repeatedly reminding either leads or workers to check progress. The supervisor
must preserve the requested result, detect drift, and direct feasible work toward
verified delivery. Activity, a successful command, and a truthful unfinished
report are not substitutes for that result.

The product is an ai-kit capability, activated through a skill. The skill starts
or attaches to a Python scheduling service and registers work; it does not
pretend that instructions alone implement a persistent loop. A separate agent
performs bounded assessments and coordination. Operational sessions retain their
own context, implementation ownership and workers.

## Decisions and existing foundations

This proposal supersedes the design direction of
[the earlier orchestration brief](2026-10-25-orchestrator-supervision-and-role-routing.md).
That file remains historical proposal material, not a second active specification.

- ai-kit installation is required. Harness integration is structural, not an
  optional plugin for an otherwise standalone orchestrator.
- Prefer supervision of explicitly connected sessions over putting all work
  beneath one large orchestrating conversation.
- Activation installs or enables one owned cron entry invoking Python every
  minute. Python performs deterministic scheduling and event delivery, backed by
  persistent SQLite task storage. No model invocation is required for an empty
  tick. A symbolic tick is a transport event, not a request for generated prose.
- Store each task's next due time rather than duplicating task IDs into 60 minute
  buckets. Distinguish interval scheduling from clock-aligned scheduling.
- A skill is the operator entry point for activation, registration, inspection,
  rescheduling, pause, completion and detachment.
- Reuse the harness lifecycle and installed roles. Do not introduce a competing
  review protocol, completion certificate or automatic av hook.

The current harness already supplies request-kind boundaries, reviewed briefs and
plans, task-bound completion checks and explicit session/task binding for advisory
verification. Its checker can reject invalid evidence when invoked; it neither
forces invocation nor authenticates semantic truth. See
[the harness contract](../documentation-harness.md) and
[verification warnings](../verification-warnings.md).

The earlier brief records OpenCode-specific orchestration/watchdog findings.
Those findings are leads for implementation discovery, not freshly verified
cross-client capabilities. Reuse or replacement must follow inspection of the
current sources. Do not copy a runtime-specific watchdog and claim portability.

## Observations informing the requirements

The supervised session exercise exposed concrete failure modes:

- A lead stopped with acceptance still open even though independent work remained.
- Lead-selected spending caps and reserved amounts were initially presented like
  exhausted operator authorization. Reported charges, unknown costs and reserves
  needed separate reconciliation.
- An apparent provider failure included deferred operations never attempted;
  a subsequent trace lookup used the wrong owner. Empty paginated results did
  not establish absence of evidence.
- A successful later call did not explain an earlier failed user experience.
- Save succeeded in storage while the same browser page still displayed no
  saved skill. A released-source browser reproducer identified stale parent
  configuration; an independent review then found a concurrent-save race.
- Repeated refinements and superseded builds moved delivery estimates. The
  supervisor had to freeze optional changes and preserve missed deadlines.
- Supervision itself became too conversational and sometimes too detailed.
  Frequent messages and repeated checks consumed attention without new evidence.

These observations motivate requirements; they do not establish measured drift
classification accuracy or prove that the proposed service already exists.

## Required behavior

### Activation and exact ownership

One skill invocation starts or attaches to the scheduling service, establishes
its health and binds the supervisor session. Installation must not silently start
monitoring every native session. Task registration records exact runtime/session
identity, repository and worktree where applicable, authorized scope, responsible
session, expected result and completion conditions.

Never select the newest session, infer membership from a directory alone, or
control an unrelated session. Workers are included only through an established
parent relationship within the authorized task. Missing transport capabilities
produce a specific diagnostic and an honest supported mode.

A repeated activation must not create duplicate schedulers or supervisors.
Detaching supervision stops future checks and instructions for the selected
sessions; it does not cancel their independently authorized work. Cancelling
underlying work is a distinct explicit operation.

### Scheduling and durable task repository

SQLite is the operational source of truth, not the conversation or an in-memory
dictionary. Keep tasks, executions and audit events, including:

- Task instruction, owner session, target sessions, scope, acceptance criteria,
  schedule, next due time, task state and optional harness references.
- Execution identity, scheduled/start/finish times, execution state, last useful
  result, evidence references, errors and bounded resource allowance.
- Creation, reassignment, assessment, rescheduling, intervention, pause,
  completion, failure and detachment, with actor and reason.

The agent uses validated operations; it does not rewrite the database freely.
Transactions and execution ownership prevent concurrent or duplicate claims.
Persist timestamps for recovery; use appropriate monotonic timing for running
process deadlines. Define behavior for clock changes, sleep and restart.

At each tick the service dispatches only due work within configured concurrency
and resource bounds. A running task cannot overlap itself. Missed periodic
checks coalesce into one overdue check, rather than a burst of catch-up calls.
One slow assessment must not block unrelated deadlines. A disconnected runtime
must not cause an unbounded retry loop.

Keep task lifecycle separate from individual execution outcomes. A failed check
need not mean the underlying assignment has failed. Supported task outcomes
include active, paused, blocked, failed, completed and cancelled; completed means
verified success, failed retains the unmet result, and blocked retains a concrete
resumption condition. Paused or cancelled work is never resumed by a timer.
Finished tasks leave the due queue but retain history. Recurring monitoring has
an explicit end condition or remains scheduled until paused/cancelled.

### Persistent supervisor memory

Persist more than task schedules: retain operator decisions and corrections,
authorization provenance, acceptance changes, verified results, unexplained
failures, attempted interventions and their outcomes, remaining obligations and
next actions. Each memory item needs scope, source, time and supersession links;
observations and hypotheses remain distinct. Preserve history when corrected.

Before assessing work after restart, compaction or a session change, restore a
bounded current memory view with references to retained evidence. Do not reload
all historical transcripts every tick. Memory must prevent repeated failed
interventions and forgotten constraints without turning stale conclusions into
current truth. Store it through the same validated persistent interface, with
transactional updates and explicit ownership rather than competing free-form
JSON and database copies. The skill teaches these operations and the orchestration
rules; Python supplies timing, persistence and transport, not semantic judgment.

### Assessment and intervention

A due check gathers changes since the last observation, not the full transcript
on every minute. Deterministic observations establish activity, elapsed time,
command results and gate status. Semantic assessments judge relevance against
the task's current acceptance conditions and retain uncertainty.

Check the lead as well as its workers. Record the current action, last useful
result, remaining obligation, actual blocker and next justified action. Recognize
legitimate long-running tools, research and external waits. Neither quietness nor
frequent output alone establishes useful progress.

Intervene proportionately: request a concrete checkpoint, redirect work, stop
optional expansion, or use an authorized interruption/recovery action. Control
requests require outcome acknowledgement; a failed stop is not a stopped worker.
No automatic destructive action or additional authority follows from a timeout.

Preserve failures alongside subsequent successes. Require evidence from the
actual failing path before calling a defect fixed. Distinguish source findings,
controlled browser tests, live runtime observations and unverified assumptions.
Keep operator corrections authoritative, including changed acceptance scope.

Bound every delegated task and assessment. The scheduler must detect an overdue
supervisor execution too; a second supervisor hierarchy is not required. Retain
failure state and a bounded recovery policy if the supervisor is unavailable.
Do not claim semantic supervision is healthy merely because Python is alive.

### Harness integration

Development tasks link to the canonical repository/worktree, brief, execution
plan, completion task ID and evidence references. Repository documents remain
the source of development intent, lifecycle and reviews; SQLite owns scheduling,
execution history and operational observations. Derived lifecycle status must
retain its source and freshness, not become a conflicting second plan.

The responsible repository lead performs orientation and required lifecycle
work. The supervisor checks applicable gates and their current evidence, routes
work through installed roles, and challenges unsupported completion. It does not
rerun doc-start or the entire review chain on every tick, impersonate reviewers,
write their approvals or advance baselines on their behalf.

Completion requires the task's acceptance conditions and applicable harness
closure, not just a green mechanical command. Changed source or scope can make
older evidence insufficient. Operational monitoring tasks still belong to ai-kit
but do not acquire a development brief/plan solely because they have a timer.

Unsupported harness versions are diagnosed, not silently migrated. Runtime
transport adapters and harness evidence adapters have distinct responsibilities;
a missing native session binding must not be hidden by successful repository
checks.

### Authority, cost and operator communication

Record the provenance of limits: explicit operator constraints, inherited
repository rules, or supervisor planning decisions. Preserve reported charges,
unknown amounts and reservations separately. Reaching a self-imposed checkpoint
requires reassessment, not inventing a user prohibition or silently buying more
attempts. Existing authorization persists; the scheduler grants none.

Supervision has its own visible cost and concurrency allowance. Routine ticks
and unchanged healthy checks remain quiet. Notify the operator of a meaningful
result, drift requiring intervention, a real blocker or a decision requiring
input. Provide an inspectable team status without per-minute conversational noise.

## Scope and delivery boundaries

In scope: supervisor skill, Python scheduling service, SQLite task/execution/event
repository, exact session bindings, harness integration, transport capability
reporting, bounded supervision/recovery, and owned installation/removal.

Initial native acceptance should target the actual interactive Codex environment
used in the observed exercise. The shared contract must accommodate Claude and
OpenCode, but neither receives a support claim without its own native evidence.
The implementation plan must state the first release's supported adapters rather
than silently promising universal session control.

Out of scope: replacing ai-kit lifecycle gates, a new model router, autonomous
budget expansion, automatic av/per-answer interception, a second implementation
lead that duplicates each session, broad operational changes, or migration of
unrelated repositories. This brief authorizes no implementation, deployment,
service startup, session attachment or paid acceptance trial.

## Acceptance for eventual implementation

1. Activating twice creates one effective service; supported real-session binding
   and an inspectable scheduler/supervisor health state are established.
2. With a one-minute tick, a ten-minute task executes when due; idle ticks invoke
   no model. One-shot and longer-than-hour schedules work without minute buckets.
3. Restart, sleep, clock changes and overlapping ticks preserve task ownership,
   limits and history without duplicate execution or replayed external actions.
   Uncertain delivery is reconciled rather than advertised as exactly-once.
4. An overdue supervisor or worker is detected independently of its own promise
   to check itself. Slow work does not block all due tasks. Recovery stays bounded.
5. A productive quiet worker and a noisy drifting worker receive different,
   evidence-backed assessments. Long-session evaluation reports missed drift,
   false interventions, detection delay and supervisory cost.
6. A lead claiming completion with unmet acceptance is redirected to feasible
   authorized work. A genuine input/authority/external blocker is retained without
   repeated futile retries. A failed attempt remains visible after a later pass.
7. A real harness-backed task retains exact brief/plan/completion bindings and
   respects fresh reviews and changed evidence. An operational timer task works
   without an invented development lifecycle.
8. Pause, cancellation, completion and detachment survive restart. Detachment
   leaves the operational sessions running and stops supervisor instructions.
9. Installation, upgrade and removal preserve foreign assets, existing session
   work, manual av and task history under an explicit retention policy.
10. Persistent memory restores operator corrections, authorization, unexplained
    failures and attempted interventions after context loss. Superseded decisions
    remain historical and are not reapplied as current instructions.
11. Deterministic CLI/service/SQLite tests precede bounded native trials. Native
    adapters are exercised through the real user activation path; fixtures alone
    do not prove wake-up, message delivery, control or behavioral improvement.

## Questions the implementation plan must resolve

- Which supported native interface can independently wake the supervisor and
  read/message/control explicitly bound sessions after the activating turn ends?
- Define the owned cron entry, Python invocation, locking and removal semantics,
  plus queued delivery when the native application or machine is unavailable.
  Cron is the chosen periodic trigger; do not return that decision to the operator.
- Which existing harness commands expose sufficient versioned evidence, and what
  minimal adapter surface is missing without duplicating its records?
- What are the default assessment/recovery/concurrency allowances and storage
  location, permission and retention rules? No hardcoded operator home paths.
- Which existing OpenCode components merit reuse after inspection, and which
  runtime capabilities remain explicitly unsupported in the first release?

The engineering lead owns these technical decisions and their verification; they
are not unresolved product questions for the operator. These decisions are not permission to substitute
an instruction-only timer or claim a background supervisor that cannot wake.

## 2026-10-27 correction — supervisor owns completion

OPERATOR > SUPERVISOR > CONNECTED LEADS > THEIR WORKERS.
Completion mandate: drive authorized work to verified completion; idle lead is
an action condition, not a veto. Wake/restart its conversation without asking
the operator to manage it. Current explicit operator pause/cancel overrides;
a later explicit completion mandate supersedes an older stop for that same work.
Preserve scope, spending and release constraints. Observation-only mandates remain
read-only. Blockers retain evidence and resumption conditions, never fake success.
Supervisor-selected reserves require reassessment, not silent abandonment.
Keep assessments short; route lengthy authorized repair to execution ownership.

Current delivery: strengthen skill entry and policy in telegraphic English;
install those reviewed instruction assets only. No scheduler/schema change,
operational task migration, target messages, commit or release. Verify installed
bytes and independent scenario decisions (idle, incomplete yield, pause/resume,
old stop/new mandate, read-only, blocker, pending intervention, budget, repair).
This establishes instruction delivery and scenario behavior, not universal native
obedience. Actual operational recovery remains a separately bounded live test.

## 2026-10-27 addition — explicit supervisor end

UX: `$supervisor end` ends the current exact supervisor binding.
FIRST: fence scheduled work; remove only its state-root cron when no other active
binding needs it. Preserve task/memory/audit history and all foreign cron entries.
DISCOVER: exact target roots + verified descendants; list native active turns.
ASK per active session: "Do you want to stop the session NAME?" Include exact ID;
no answer or No means no interruption. Never infer stop approval from end alone.
STOP: only confirmed session and observed turn; changed turn requires fresh
confirmation. Verify native state after interrupt; report pending queues and
unmanaged subprocess uncertainty. No process kill, archive, restart or deletion.
Partial native/cron failure must retain truthful cleanup results and retry path.
Install command/policy support; do not execute end on operational sessions as
part of implementation. Native capability testing uses isolated fixtures only.
