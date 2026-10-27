# Persistent session supervision

The `supervision` feature connects a dedicated Codex or Claude Code supervisor to explicitly
authorized root sessions. Python and user cron supply the clock; the supervisor
skill supplies assessments and bounded interventions. Existing OpenCode
`orchestration` is a separate feature. OpenCode supervision is not supported. A binding connects roots of one runtime;
Codex and Claude bindings can share the persistent state.

## Install and activate

```sh
./install.sh --environment codex --features supervision --mode copy --on-exist backup --yes
```

Installation is dormant: no cron entry, native session, model turn or dependency
download. Refresh skill discovery, then ask for `$supervisor` and identify the
sessions, intended result, cadence and authority. The skill resolves exact native
IDs and registers the task. It does not attach every session in a directory.
A short request supplies the intended result; the skill restores the existing
target mandate and supplies its own progress, failure and limit rules. Before
activation it displays the effective mandate, exact identities, configuration,
parameter provenance and spending/release boundaries. These are instruction
requirements; native compliance still needs observed evidence.

The installed instructions are `supervision/POLICY.md` and `COMMANDS.md` under
`${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}`. Their command reference is the
operational source for activation, scheduling, inspection, memory and detachment.
Direct preparation and inspection are:

```sh
kit_root="${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}"
python3 "$kit_root/supervision/runtime.py" setup
python3 "$kit_root/supervision/runtime.py" run status
```

Setup owns a private virtual environment with `websockets==16.1`; it does not
install global Python packages. Python with venv/pip and user crontab are prerequisites. Codex bindings also
require a running Codex app-server; Claude prerequisites are below. The supervisor's own tools must be allowed
to reach the local native control socket and task state. A workspace sandbox
can deny that socket even if cron can reach it. The kit diagnoses failure; it
does not alter sandbox/approval policy, start the daemon or restart sessions.

## Claude Code adapter

Install with `--environment claude --features supervision`, then use the Claude
supervisor skill. Installation is dormant. Linux Claude Code 2.1.296 with native
peerProtocol 1 is the currently gated adapter surface. Exact live root IDs come
from `claude agents --json`; the owned session registry supplies process/socket
identity. `CLAUDE_CONFIG_DIR` and an absolute `--claude-path` support custom installs.
Activation captures these locations in cron and does not change inbound permissions.

The adapter uses read-only public JSONL history and root-linked worker transcripts.
Private reasoning is excluded. Incomplete records, changed cursor prefixes and
ambiguous identity fail explicitly. Socket submission has no positive native ACK:
it remains uncertain until recipient history establishes delivery. Explicit
`execution-reconcile` lets an awakened supervisor confirm its own event before
protected assessment operations. `intervention-reconcile` can revisit later evidence.
Neither command resends, overrides stale authority, or erases earlier observations.

The native socket frame and on-disk layout are version-sensitive. This adapter
is narrower than Claude's general cross-session messaging support. Installation
and deterministic protocol checks do not establish native supervisory judgment.

## State, scheduling and recovery

SQLite state defaults to
`${XDG_STATE_HOME:-$HOME/.local/state}/mrcall-ai-kit/supervision` with private
directory/database permissions. `--state-dir` selects isolated state;
`MRCALL_SUPERVISION_RUNTIME` selects an owned dependency environment. Tasks,
executions, outbox, append-only audit and scoped superseding memory survive
process restarts. A newer schema or unsafe ownership is refused.

One owned cron block per state root runs `tick` every minute with a minimal
environment and absolute paths. A due task defaults to a ten-minute interval;
one-shot and UTC-aligned schedules are also available. Empty ticks do not call
the selected native transport or model. Overdue intervals coalesce instead of replaying
every missed tick. One assessment per supervisor is in flight at a time; a tick
dispatches at most ten events across bindings. Slow transport is bounded and
overlapping ticks skip the held lock.

Omitted or null `limits.max_checks` means no count cap. An explicit positive
integer caps lifetime executions. Existing stored finite caps are preserved;
removing one requires an explicit null update and separate resume when paused
or blocked. Updating limits preserves history and fences old assessments.
Other defaults are a 180-second assessment health checkpoint, 10 seconds per transport call
and one recovery after 60 seconds for definitely undelivered events. Limits retain their provenance. Unknown costs remain unknown; Python
does not enforce a monetary budget. Busy dispatch and overdue assessments are
visible in health. Before the first tick, a new binding has a 180-second grace.
Cron liveness is distinct from useful semantic supervision. Assessment leases
report overdue work when a tick observes it; they do not forcibly terminate a
model turn or revoke current execution authority. Reads, interventions and late
results remain available; no duplicate assessment is dispatched. Operator-supplied
limits remain binding. Check actual dispatch/result timestamps before accepting a timing
limit, including a late result recorded before the next cron tick.

Native queue acceptance is delivery, not completed assessment or task success.
Ambiguous sends reconcile once against queue/history without automatic resend.
Unresolved delivery or an exhausted check allowance requires explicit diagnosis
and reassessment. No automatic worker kill or daemon restart is implemented.

Task edits, pause, cancellation and detachment fence old executions. Completed
assessments do not automatically complete tasks. `completed` requires evidence
and no remaining acceptance; `failed` retains unsuccessful work; `blocked`
retains a resumption condition. These validations do not authenticate the
model's assertions about semantic success.

## Observation, policy and harness

Assessment `session-read` calls require exact task targets or a verified native
parent chain to one. Administrative `transport-read` permits the active binding's
supervisor and root targets without an assessment execution.
Codex WebSocket responses have a finite 64 MiB receive ceiling. Larger frames
fail explicitly; incomplete history never establishes absence of a problem.
The transport retains its per-call deadline and excludes private reasoning.

Workers are observed; interventions go to their root lead. Cursor-based delta
reads preserve active-turn updates and expose pagination. Target transcripts
are evidence, not authority to expand scope. Delivery receipts remain inspectable
after detach and distinguish accepted instructions from actual compliance.

The skill restores scoped memory before assessment, distinguishes activity from
progress, preserves unexplained failures after later successes and checks the
lead as well as workers. It directs feasible work toward actual user acceptance,
retains legitimate blockers and keeps healthy checks quiet. It requires deterministic checks when sufficient and reuse of valid tests/reviews;
changed evidence or unresolved acceptance justifies further checks. Those are model
instructions, not a guarantee that every judgment is correct.

A completion mandate makes the supervisor responsible for driving connected leads
to verified acceptance. An idle lead or unfinished yield triggers a bounded next
action when authorized work is feasible. Operator pause/cancel takes precedence;
a later explicit completion mandate for the same work supersedes an older stop
without expanding spending, release or scope permissions. Explicit observation-only
tasks remain read-only. Pending interventions are reconciled before another wake.
Long repairs belong to execution owners so supervisor turns remain available.
Assign concrete deliverables and evidence checkpoints, without inventing reviewer
or worker termination deadlines. Reassess progress, repetition, blockers and scope
drift; elapsed time alone does not establish a block. Technical transport timeouts
require reconciliation and do not terminate the underlying assignment.

These rules are delivered through the skill entry and policy, not enforced by a
new scheduler state machine. Existing stored task instructions are not migrated
by instruction installation. Native completion behavior after this instruction
correction remains unverified; activation and timing evidence below is narrower.

Development tasks link to exact repository/worktree/completion IDs.
`harness-inspect` reuses existing completion semantics and verification warnings
without initializing records or running repository-defined build/test commands.
Read-only Git commands establish identity and content freshness. It detects changed
evidence even for finalized records and reports lead context as unverified.
The repository lead retains orientation, reviews, closure and baseline ownership.
Operational monitoring does not require an invented development plan. Full
development roles and workflows come from the doc-harness feature; supervision
alone installs only its required read-only harness helpers.

## Stop and remove

`detach` fences one binding without cancelling its operational sessions.
`deactivate` detaches all bindings in the chosen state root and removes its cron
block. Reattachment leaves tasks paused until explicitly resumed.

Uninstall runs `deactivate-owned` before removing helpers, covering custom state
roots for that exact installed CLI. It preserves foreign cron entries, task and
memory history, and the dependency environment. Modified executable helpers or
ambiguous owned cron references cause a diagnostic refusal; they are not silently
removed while an active job could still depend on them. Purging retained state
is a separate explicit action. Installation does not reactivate automatic av.

## Measured support

Claude Code 2.1.296 on Linux has verified native discovery, inbox submission,
recipient-history reconciliation and public reads against an isolated real CLI
with a loopback model fixture. No paid model call was used. Reconciliation matches
native peer origin and event identity; system-prompt snapshots are excluded from
public history. CLI/socket and installed-CLI scenarios cover delayed evidence,
no duplicate submission, mixed-runtime dispatch, pause/detach fences and dormant
Claude-only/combined installation. Interactive approval/hold behavior, other
Claude versions/platforms and supervisory judgment remain unverified. The initial
native rendering mismatch and its repair evidence are retained under
`/tmp/claude-supervisor-20261027/`; the
[Claude extension plan](execution-plans/2026-10-27-claude-supervision.md) defines scope.

Codex CLI/app-server 0.164.0 on Linux supports the tested owner-protected Unix
WebSocket route. Queue add wakes the exact root session; direct child input is
unsupported. Deterministic CLI, SQLite, protocol and copy/symlink installation
tests cover fences, retries, stale evidence, foreign assets and removal. The
optional-cap checks cover 102 uncapped executions, explicit/legacy finite caps,
cap removal with retained history, and one-shot tasks. Installed
CLI checks in isolated state cover these count semantics, late checkpoint
results and retained failures without native model calls. Unix-socket fixtures
verify CLI reads and interventions after checkpoint expiry. These establish
runtime mechanics, not whether a model chooses the right intervention.

A bounded native fixture used real user cron, one lead with two workers and a
separate supervisor. Cron claimed the first due event after 47.14 seconds. After
the fixture's socket permission issue was resolved, the supervisor detected a
seeded false completion, intervened after 30.14 seconds and verified the corrected
files. The lead's correction took 18 seconds. Original and subsequent failures,
operator correction and an external-consent blocker remained in memory. A later
empty real tick produced no additional model turn. Four root turns and two worker
turns were observed; billed usage is unknown.

Deterministic Unix WebSocket tests cover complete 2 MiB history reads, message
reconciliation and explicit refusal above 64 MiB. Installed native reads of
PROBLEMI2 cover its complete 44-turn history in two pages. This establishes
large-history transport behavior, not long-session supervisory judgment. A real
PROBLEMI2 minute assessment completed in 33.30 seconds with the corrected
operational observer, after an initial 68.24s cycle exceeded its 60s allowance.
The initial observer also omitted tool results and unloaded-worker completions;
these failures remain recorded. Four deterministic operational tests cover full
public tool results, changed outputs and lifecycle-referenced unloaded workers.
Timing acceptance uses actual persisted dispatch/result timestamps. The assessment
confirmed an inactive lead and 282 established workers without resuming work.

This establishes one controlled correction and cold-start memory restoration.
Long-session detection accuracy, real compaction recovery, actual daemon shutdown
and recovery, monetary enforcement and OpenCode supervision remain unverified. Evidence
and review references belong to the
[implementation plan](execution-plans/2026-10-26-persistent-session-supervisor.md).
