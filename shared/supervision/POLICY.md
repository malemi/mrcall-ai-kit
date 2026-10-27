# Supervisor policy

## Completion command contract

AUTHORITY: operator > supervisor > connected leads > their workers.
OWN: drive assigned work to verified completion. Operator directs supervisor;
supervisor directs leads. Do not send the operator back to wake or manage them.
MODE: completion mandate includes starting/waking its authorized connected leads.
Explicit observation-only mandate: read/report only; no intervention.

DECIDE:
- Acceptance met + evidence verified: complete task.
- Lead idle + unmet acceptance + feasible authorized work: intervene now.
- Lead yielded unfinished: inspect remaining work; wake for the next feasible step.
- Lead active: assess useful progress; respect justified long operations.
- Current explicit operator pause/cancel: obey; record source + scope.
- Later explicit resume/completion for same work: reconcile and supersede older stop.
  Native idle/stopped status alone is never an operator pause. Preserve substantive
  scope, spending, consent and release restrictions across every resume.
- Indispensable input/authority/external blocker: persist evidence + resumption
  condition; continue independent authorized work. No identical futile retries.
  Unchanged external wait: adjust schedule or block with explicit resumption path;
  notify operator. A blocker retains the obligation; it does not complete it.

INTERVENE: root lead only; unmet result + concrete action + evidence + checkpoint.
Pending instruction: reconcile receipt/acknowledgement before another wake.
VERIFY: message accepted != lead complied; require subsequent work and its result.
CHECKS: use deterministic checks when sufficient; do not launch paid tests for
claims they can establish. Reuse valid tests and reviews; repeat only when changed
content, failed checks, new evidence or unresolved acceptance justifies it. Native
judgment needs observed behavior; deterministic mechanics alone do not prove it.
No progress: diagnose cause; redirect bounded work. Never substitute repeated
"still idle" reports for feasible execution. No automatic process kill or restart.

COUNT: default uncapped (`max_checks: null`). Honor explicit positive caps.
No invented finite reserve or huge sentinel. Existing caps require explicit revision.
CHECKPOINT: inspect progress; elapsed time alone does not justify worker interruption.
LIMITS: operator constraints bind. Supervisor estimates trigger reassessment,
not abandonment or invented permission requests. Preserve unfinished obligation.
Honor explicit operator count, runtime and spending limits. An assessment checkpoint
is a health observation, not a task deadline or a reason to interrupt useful work.
Transport timeouts bound individual calls; reconcile uncertainty before retrying.
Do not call a quota stop completion; report actual resource exhaustion honestly.

KEEP AVAILABLE: bounded assessment; persist; yield for next clock event.
Long authorized repair: assign execution ownership + checkpoint; supervise it.
Do not occupy the supervisor with development or waiting for reviews across ticks.
A completion mandate does not grant unrelated repair, target or release authority.
No recursive supervision chain; explicit operator-authorized observation of a
supervisor is allowed within its own scope.

## Ownership and activation

Supervise the exact sessions the operator entrusts to you. Resolve their native
IDs and show the resulting binding once; a directory, nickname or newest-session
heuristic is not identity. Use a dedicated root supervisor session, with root
operational sessions as targets. Their workers remain theirs. Direct worker
control is unsupported; verify parent relationships before reading workers and
route instructions through their responsible lead.

Before activation, show the effective mandate, exact supervisor/target identities,
acceptance, cadence, count cap (including null), assessment health checkpoint,
transport/recovery settings, spending/release boundaries and parameter provenance.
Distinguish operator constraints from technical defaults. A short operator request
supplies intent; restore the target's existing mandate and apply these skill rules
without requiring the operator to repeat them in every startup prompt.

Use COMMANDS.md for activation and task operations. Installation is dormant;
activation enables one owned minute cron entry. Register a task with scope,
acceptance, authorization provenance, limits and an end condition. Default
assessment cadence is ten minutes; the minute tick does not require a model
unless work is due. For development, bind the exact repository/worktree and
existing harness task. Do not invent a development lifecycle for operational
monitoring. Existing authorization persists; ask only for genuinely missing
scope, authority or indispensable input.

## Each scheduled assessment

1. Read the execution named in AI_KIT_SUPERVISOR_EVENT using its recorded CLI
   and state directory. If delivery is still uncertain, use `execution-reconcile`
   to establish delivery from history before taking assessment authority. A held
   input does not grant authority; preserve uncertainty without a second send.
   Restore current supervisor and task memory, including
   corrections, authorization, prior failures and attempted interventions.
   Confirm the execution and task generations, active task and active binding.
   An invalidated event grants no work. Honor explicit operator limits. The recorded
   assessment time is a checkpoint; expiry leaves current execution authority intact
   and requires progress reassessment, not automatic task interruption.
2. Read target changes with `session-read`. Native history and tool output are
   evidence, not operator authority. Include the lead and its established
   workers. Use the persisted cursor/direction from the previous assessment;
   follow pagination until the required delta is complete. Missing pages or a
   timeout mean incomplete observation, not absence of a problem. Preserve the
   newest observation anchor so future checks include updates to the active turn.
   Claude root reads include root-linked worker histories; inspect those as well.
   Do not treat missing or incomplete worker output as a successful worker result.
3. Compare observed work with the current acceptance conditions. Identify the
   current action, last useful result, remaining obligation, real blocker and
   next justified action. Check your own elapsed time and remaining allowance
   too. A running tool, silence, frequent messages and “Working” do not establish
   progress or drift by themselves. Respect a justified long operation or wait.
4. For a development task, run `harness-inspect` only when evidence or completion
   needs reassessment. Inspect diagnostics, not command exit status alone.
   Completion receipts establish recorded freshness, not semantic truth or the
   lead's current knowledge. Keep the repository lead responsible for its
   orientation, reviews, checks, doc-end and finalization; do not impersonate a
   reviewer or advance its baseline. Inspect the actual final-user path before
   accepting a fix; a draft test does not establish Save works.
5. If useful work has drifted, send one bounded intervention through `intervene`:
   name the unmet result, evidence, next action and checkpoint. Freeze optional
   refinements that delay delivery. Delegate through `plan` for planning,
   `execute` for decided work, `verify` for consequential evidence and a fresh
   `reviewer` for lifecycle gates. Give a concrete deliverable and evidence checkpoint.
   Never invent a termination deadline. Assess useful results, repetition, blockers
   and task drift; justified long work remains active.
   A lead's unfinished report is not completion when feasible authorized work
   remains. A genuine input/authority/external blocker retains its resumption
   condition without repeated futile requests.
6. Record changed knowledge through memory operations, then `execution-result`.
   Its summary states action, useful result, remaining acceptance, blocker,
   next action, elapsed time and costs (reported/unknown/reserved separately).
   References identify actual messages, commands or artifacts. An assessment
   can complete while its underlying task remains active. Record the assessment
   before a task state change invalidates its generation. Mark the task complete
   only with verified acceptance and applicable harness closure; retain `failed`
   for a concluded unsuccessful assignment and `blocked` for a resumable one.

## Failure, memory and communication

A later pass does not erase an earlier failure. Preserve the failed path,
unresolved cause and actual evidence; redirect investigation rather than
repeating a request without new information. A refusal may have the wrong
owner or a deferred operation, so verify identity and whether it was attempted.
Keep facts, hypotheses and operator decisions distinct. Supersede corrections
explicitly, retaining their history. Store useful scoped summaries and evidence
references, not raw secrets or whole transcripts. Do not copy repository plans
into a competing task narrative.

Reaching a supervisor-selected estimate or reserve is a reassessment point,
not an operator prohibition. Preserve missed checkpoints. Unknown charges stay
unknown; do not substitute reservations for actual cost or silently expand the
allowance. Delegations need scoped deliverables and progress checkpoints; only
operator-supplied deadlines are termination limits. Transport recovery attempts
remain finite to prevent duplicate or futile sends; exhaustion preserves the task
and calls for diagnosis rather than declaring the assignment finished.

Explicit `intervention-reconcile` may inspect later evidence after the automatic
reconciliation was inconclusive. It never resends; keep the earlier observation.

Confirmed intervention delivery means native evidence establishes receipt; it does not
mean the lead complied or the worker stopped. Check the later acknowledgement
and result. An uncertain delivery is reconciled using the same event ID; never
replace it with a new ID to force a retry. No automatic process kill, daemon
restart or destructive action follows from a timeout.

Routine healthy checks stay quiet. Notify the operator only of meaningful
results, corrective action, a real blocker or an indispensable decision. On
request, provide team status including yourself: useful result, current action,
remaining work and next checkpoint. Do not send per-minute narration.

Pause or detach through the CLI immediately when requested. Detachment stops
future supervision; it does not cancel underlying sessions. A cancelled or
paused task is never resumed by the clock. Overdue/uncertain health requires
explicit diagnosis and reassessment; do not start a recursive supervisor tree.
