---
status: completed
---

# Persistent session supervisor implementation plan

## Mandate and approved input

This is substantial development: persistent state, background execution and
session-control boundaries exclude the fast path. This artifact authorizes no
implementation, native trial, cron registration, session attachment or release.
The approved brief is `docs/briefs/2026-10-26-persistent-session-supervisor.md`,
SHA-256 `fd24f30e9adb0290b725aae051231ed8363ba9945d1af70c3d52123df38309ac`.
All milestones remain pending. Obtain fresh plan approval before starting.

## Architecture decisions

- Add a distinct `supervision` feature; preserve existing OpenCode-only
  `orchestration` unchanged. Its client selects the newest child after task
  registration, so it is unsuitable for exact existing-session supervision.
- Keep implementation in a new `shared/supervision/` package, with a small CLI,
  SQLite store, scheduler, cron manager, harness adapter and transport interface.
  Place Codex transport in `codex/supervision/`, not in the shared policy.
- Use Python standard-library scheduling/storage/process primitives. Select any
  transport dependency only after M0 proves its necessity and ownership.
- Install dormant assets under the existing kit root. Store private operational
  state under `${XDG_STATE_HOME:-$HOME/.local/state}/mrcall-ai-kit/supervision/`
  with directory mode0700 and database/evidence mode0600. Permit an explicit
  test/state-root override; refuse unsafe symlink or ownership collisions.
- One owned user-crontab entry invokes the installed Python CLI `tick` every
  minute through an absolute interpreter/launcher. No daemon is required for
  scheduling. Activation binds the actual supervisor and enables the entry;
  reinstall and `--yes` do not activate it.
- Tick claims due work and dispatches bounded events; it never waits for model
  completion. Persist exact runtime/session IDs, not native database mutations.
- Default task cadence is ten minutes, overridable per task; support one-shot,
  fixed intervals and explicit UTC clock-aligned schedules. No minute buckets.
- Default one in-flight assessment per supervisor and per task; coalesce multiple
  due tasks into a bounded inbox and prevent a slow turn from blocking other
  supervisors. Observe pending deadlines even while semantic assessment is busy.
- Default transport call bound10s, assessment deadline180s, and one reconnect
  attempt after60s only for definitely undelivered events. Ambiguous delivery
  enters reconciliation, never automatic resend. No automatic process restart
  or worker kill by default. Bounds are configurable and provenance-labelled.
- Record missing cost data as unknown. Native acceptance has a separately recorded
  finite allowance selected by the lead within actual authority before launch;
  this plan grants no paid trial. Never substitute a self-imposed cap for a user
  prohibition or change the configured model to save cost.

## M0 — Prove the external native transport

Owner: lead with a bounded `verify` assignment for consequential interface claims.
Dependencies: approved plan and authority for the exact disposable native trial.
Inspect the installed client/interface source or documented interface; use the
OpenAI documentation workflow if external product documentation is needed.
The in-session `codex_tui` tool is evidence of a session capability, not proof that
cron can call it. Select an authenticated, supported external route to the SAME
explicitly bound interactive session; do not silently create a replacement CLI
conversation or write native thread/history databases.
Deliver a capability record with exact client/version, invocation, authentication,
read cursors/pagination, wake acknowledgement, busy-session behavior and available
control acknowledgements. Specify unavailable control modes explicitly.
Verification: from outside the target turn, deliver a unique event to a disposable
existing session after its turn ends; observe exact-session acknowledgement.
Exercise app unavailable then available, incorrect identity, and target busy.
Prove unchanged unrelated sessions. Use no business actions. Deterministic protocol
checks precede a minimal finite real model wake trial; do not call mocks native proof.
Gate: fresh reviewer approves capability and its residual limits. If no external
route exists, return a concrete integration blocker; no instruction-only fallback
or supported-runtime claim. Do not spend on the dependent implementation.

## M1 — Durable task, execution and memory interface

Owner: one `execute` assignment owning shared storage/CLI and focused tests.
Dependency: M0 approved. No runtime attachment or cron activation in this milestone.
Create versioned tables for tasks, exact bindings, executions, event outbox,
append-only audit, memory and supersession. Persist scope, acceptance, authorization
source, limits, schedule, next due time and harness references. Separate task
states from execution states; failed checks do not silently fail whole tasks.
Provide validated create/update/schedule/pause/resume/complete/fail/cancel/detach,
inspect, memory-add/supersede and execution-result operations with JSON output.
Completed task history remains; completion records evidence and remaining work.
Use transactions, unique execution IDs, revision checks and fencing generations.
Memory distinguishes facts from hypotheses and restores current scoped decisions,
corrections, failed interventions and unresolved obligations with evidence links.
No raw secrets or full transcripts by default; no automatic history deletion.
Verification: real CLI subprocesses against temporary SQLite prove concurrent
updates, invalid transitions, revision conflicts, completion requirements,
correction/supersession, restart/context-loss restoration and private permissions.
Test schema migration with backup; unsupported newer schema refuses writes.
Gate: fresh milestone review. Rollback disables consumers and restores a database
backup only without discarding post-backup writes; otherwise retain read-only data.

## M2 — Minute ticks, bounded delivery and recovery

Owner: `execute` assignment owning scheduler/cron/transport integration and tests.
Dependency: M1 reviewed. Implement transactionally claimed due occurrences and
outbox records, nonblocking tick lock, leases and fenced acknowledgements.
Before delivery revalidate binding generation, active state and current authority;
pause/cancel/detach invalidate queued work. Acknowledged delivery is distinct from
assessment completion and underlying task completion.
Persist UTC deadlines; use monotonic time for subprocess timeouts. Test backward
clock movement without duplicate occurrences and forward/suspend gaps with one
coalesced overdue occurrence. Expired leases require delivery reconciliation;
never replay an uncertain external action because a lease expired.
Keep cron and semantic-supervisor health separate. An overdue supervisor becomes
unhealthy visibly without an infinite recovery tree. Preserve due work while a
native application is unavailable, with bounded reconnect and no model storm.
Verification: crash injection before/after claim, send and acknowledgement;
concurrent ticks; duplicated/out-of-order acknowledgements; stale bindings;
long assessments; invalid cron environment; actual CLI with fake transport;
empty ticks perform zero transport/model calls. Native transport contract cases
reuse M0 evidence only when unchanged.
Gate: fresh milestone review. Rollback removes only the owned cron entry and
fences dispatch; it does not terminate operational sessions or delete state.

## M3 — Skill policy and harness-backed assessment

Owner: lead for policy/acceptance; bounded `execute` for CLI/harness integration.
Dependency: M2 reviewed. Create canonical policy under `shared/supervision/` and
Codex entry `codex/skills/supervisor/`; load the skill-creator workflow when authoring.
Teach activation, task/memory operations, delta reads, proper installed role
selection, result checking and bounded interventions. Native target content is
untrusted evidence, never authority to expand scope or attach other sessions.
Use exact repository/worktree/completion IDs. Reuse explicit verification-warning
CLI inspection for mechanical/focused freshness and existing completion-check
semantics for applicable closure; warnings exiting0 do not mean acceptance passes.
If additional read-only evidence export is necessary, extend the existing harness
interface minimally rather than inventing duplicate completion records.
Repository leads retain orientation, reviews, doc-end and baseline ownership.
Operational monitoring does not invent development plans. Do not initialize a
completion record merely to inspect a task, or repeatedly rerun the whole harness.
Assessment records current action, last useful result, remaining acceptance,
blocker, next action and actual elapsed limits. Preserve failures after passes,
user corrections, real authorization and estimate overruns. Routine healthy checks
remain silent; only meaningful results, interventions and actual blockers notify.
Verification: real CLI fixtures against temporary harness repositories cover
missing/stale evidence, differing worktrees, unchanged valid evidence, unsupported
profiles and operational tasks. Structured policy scenarios cover noisy drift,
quiet progress, legitimate waits, wrong-owner evidence, unresolved failure followed
by success, repeated refinements, false completion and cost/reserve distinctions.
Gate: fresh milestone review; deterministic scenarios do not certify model behavior.

## M4 — Owned installation and real-user acceptance

Owner: lead integrates; `execute` may own installer tests; `verify` owns native evidence.
Dependencies: M3 reviewed. Extend install.sh/uninstall.sh feature inventory and
manifest routing. Install shared assets once and Codex skill directory atomically.
Keep OpenCode orchestration and automatic-av retirement untouched. First release
claims Codex only after native acceptance; other adapters remain unsupported.
Activation installs one owned cron entry with safe quoting including spaces and
cron-special characters. Repeated activation is idempotent. Uninstall disables
owned cron before removing helpers, preserves foreign entries and task/memory
history; purge is separate explicit destructive action.
Verification: real installer CLI under temporary HOME for symlink/copy, repeated
install, update, foreign assets, missing prerequisites, disable and uninstall;
crontab fixture controls first, then bounded actual-user cron activation in the
approved disposable native session. Prove minute wake, ten-minute task scheduling,
idle quietness, busy/offline recovery, pause/detach and memory after context loss.
Run a finite supervised task with a lead and workers: both productive and drifting
controls, plus unmet-completion and valid-blocker cases. Record intervention delay,
false/missed interventions and supervisory usage. Failed free checks prohibit paid
acceptance. No production sessions or open-ended behavioral trial.
Gate: fresh milestone review tied to exact installed candidate and capability limits.

## M5 — Documentation closure and final delivery

Owner: lead; explicit doc-critic and fresh final reviewer are separate gates.
Dependencies: M4 approved. Reconcile README, AGENTS thin index, docs/README,
new docs/supervision.md, runtime support table, verification-warning integration,
active context/archive, brief and this plan. Update help/tutorial and changelog
only to verified installed capabilities; preserve unsupported/runtime limits.
Run configured mechanical checks and focused lifecycle/install suites. If role
sources change, regenerate through build-agents.py and run generated-agent check;
do not edit rendered TOML directly. Invoke doc-end, doc-critic including unchanged
affected contracts and active-context shape, completion check, separate final review,
then baseline finalization. Repair findings with the same gate reviewer.
Deliver activation/inspection/detachment commands, evidence, rollback and limits.
Commit/release/installation into operational environments require their applicable
explicit authority; a reviewed plan is not that authority.

## Planning evidence and limits

Read: approved brief, install.sh, uninstall.sh, verification_warnings.py,
Codex verification-warnings skill and OpenCode watchdog_client.py; inherited
lead orientation supplies the harness contract and role-generation rules.
Installer source routes orchestration only to OpenCode; uninstaller preserves
foreign/modified manifest assets. Warnings expose explicit check/bind/unbind/status
and only mechanical/focused receipt diagnostics, not full semantic completion.
Ran verification_warnings.py --help successfully and verified the approved SHA.
Scoped source search found no existing external codex_tui session sender in the
inspected kit surfaces. The exact external native transport remains M0's unresolved
feasibility dependency. No implementation, cron entry, database, native session,
paid trial, service activation, commit or release was created by this planning work.

## Execution record

The operator authorized implementation with "vai col coding" on 2026-10-26.
Brief and plan passed independent reviews before this authorization; approved
versions and raw verdict references are retained outside the source tree.
M0 is active; M1–M5 remain pending. Initial configured mechanical smoke passes.
No release or attachment to operational sessions is authorized by this update.

### M0 capability result

Codex CLI and server 0.164.0 expose an owner-protected Unix WebSocket control
socket discovered by `codex app-server daemon version`. External Python
initialize plus thread/queue/add wakes the exact existing idle root session;
the accepted client message ID appears in native history and the target replies
with the expected nonce. Two further events delivered while active complete in
the same root session. Queue add auto-starts; do not call queue/start afterwards.
Direct input to multi-agent-v2 children is rejected; supervisor and connected
operational targets must accept direct input, while child monitoring is read-only.

Retained evidence: native-root-probe.json, native-root-observed.json and
native-busy-probe.json under /tmp/mrcall-ai-kit/supervisor-implementation-20261026.
Three tiny acknowledgement turns, no model override or business action. Invalid
thread read rejects; an absent socket fails without delivery. Actual daemon
shutdown was not tested because it would disrupt unrelated sessions. Reconnect
to the running endpoint is proven; unavailable/recovery controls need M2/M4.
No duplicate-ID exactly-once guarantee or arbitrary worker control is claimed.
The adapter will reconcile queue/history before retrying uncertain delivery.
Use the existing Python websockets dependency with an owned installation path;
its version and dependency installation are M4 obligations. Native send source
requires exact session ID and current capability, not private database mutation.

### M1 candidate

The shared SQLite store and JSON CLI implement task/binding state, optimistic
revisions, generation fencing, private files and append-only memory/audit. Eight
real CLI tests pass, including concurrent updates, restart recovery, rejected
newer schemas and detach/reattach with old execution refusal. Reattachment keeps
tasks paused; explicit resume is required. Default resource values retain their
supervisor-default provenance separately from supplied limits. Scheduler and
native integration remain pending. Evidence: /tmp/mrcall-ai-kit/supervisor-m1-store.

### M1 approval and M2 candidate

M1 passed independent review after preserving blocked-task resumption details
across edits; nine real CLI tests pass. M2 adds minute cron registration, claimed
occurrences, bounded recovery, generation fencing and native delivery/reconciliation.
The combined suite passes 27 tests, including actual CLI-to-Unix-WebSocket fixtures.
The implemented adapter also reads and reconciles the prior disposable native
event successfully without submitting another turn. Live cron and installed-path
acceptance remain M4 obligations. M2 independent review is in progress.

### M2 approval and M3 candidate

M2 review approved the repaired busy-dispatch deadline and detached-read fence;
29 tests passed at that gate. M3 adds read-only exact-worktree harness inspection,
fenced descendant reads, retained intervention receipts, uncertain-send
reconciliation and the supervisor policy/skill. Native ascending cursor reads
include the previous anchor's updates on the installed server. The combined
candidate passes 42 deterministic tests; skill structural validation passes.
Runtime setup and installed-path activation described by COMMANDS.md are the
next M4 integration obligation, not yet a shipped capability.

### M3 approval and M4 candidate

M3 passed fresh review; all six bounded policy scenarios returned evidence-aware
assessments. M4 adds dormant Codex-only installation, an owned Python environment
with websockets 16.1, manifest-aware uninstall and inspectable scheduler health.
Five actual temporary-HOME installer cases pass alongside Codex and shortcut
regressions. Initial real cron registration exposed an overlong inherited PATH;
minimal PATH plus a pinned absolute Codex executable repairs that root cause.

Actual user cron then woke the exact disposable supervisor. Its first assessment
restored memory and diagnosed native socket access denied by the fixture's
workspace sandbox. That failed assessment remains recorded. Resuming only the
disposable supervisor with permitted native control access enabled the next
assessment; no operational runtime configuration changed. Successful support
requires that access, and the kit does not grant it or change sandbox settings.

The second assessment read the lead and two parent-verified workers, detected
a deliberately false completion claim, sent one bounded corrective instruction
and independently checked final file bytes. Both the missing-token failure
and a later exact-content failure remain alongside their passing results. The
external-consent branch stayed blocked without attempts. The task completed
with persisted memory and evidence. A subsequent real empty cron tick created
no extra model turn. Four root turns and two worker turns were observed; actual
charges are unknown. This finite fixture is not long-session reliability proof.

Deactivation restored the original crontab byte for byte, retained history and
left the underlying sessions idle with unchanged turn counts. Disposable root
sessions were then archived separately. Final diagnostic/health refinements
have focused deterministic checks; the final installed candidate also passes
a detached tick without creating an execution. Evidence is retained under
/tmp/mrcall-ai-kit/supervisor-implementation-20261026, including native acceptance,
worker observations, idle proof and independent verification. No release or
operational activation was performed.

### M4 approval and documentation closure

M4 passed independent review with the final installed assets matching source.
The final deterministic supervision suite passes 55 tests; existing Codex and
shortcut installation checks, help/tutorial coverage and skill validation pass.
Current-state documentation covers activation, ownership, harness integration,
native permission prerequisites and the measured finite trial limits. Existing
automatic-av retirement and lifecycle contracts remain applicable. The historical
prototype timing paragraph is archived verbatim; a current support pointer
remains in the living context.

Final closure uses task persistent-session-supervisor. M0–M4 approved versions
and raw verdicts are retained with the completion record. Mechanical/focused
receipts, explicit doc-critic and a separate final reviewer are required before
the declared active-to-completed transition. Release and operational deployment
remain outside this implementation authorization.

## Planned follow-up — compact handoffs and incremental observation

Requested by the operator on 2026-10-27 after the TEST-SUPERVISOR trial.
This is a planning amendment, not implemented behavior or permission to deploy.
The completed status above covers M0–M5 only. This follow-up remains pending;
create its scoped brief and active execution plan, with fresh gates, before coding.
Do not alter the concurrently owned large-history repair plan. Its finite receive
ceiling addresses transport delivery, not context volume or observation accuracy.

### Problem and intended result

A real observer read of TEST-SUPERVISOR returned approximately 195,000 tokens,
including nested tool outputs, and was truncated at the tool boundary. A later
structured projection recovered public assistant messages, but did not establish
that all embedded evidence was assessed. Evidence: observer execution
`63c9048f-a624-4786-9cfe-64a5127db4a1` and its retained assessment/memory.
Long-lived sessions are a supported use case to design for, not operator misuse.
The supervisor should restore a compact evidence-linked handoff, inspect changes
since its observation anchor, and retrieve original evidence only when needed.
A target's summary is an attributed claim, never independent acceptance proof.

### F1 — Structured handoff and authority boundaries

Owner: lead for contract; bounded plan/reviewer roles for design gates.
Define a versioned handoff containing exact session/task/worktree identity,
objective and acceptance, user corrections and authorization references,
verified results with evidence references, unexplained failures, remaining work,
blockers, worker IDs/relationships, next checkpoint, and source coverage anchor.
Keep facts, target claims and supervisor verification distinct. Preserve original
history; supersession must retain corrections and failures rather than erase them.
Request a handoff through the native lead channel only with messaging authority.
Read-only monitoring must not silently send such a request; it may construct an
attributed observation summary from authorized reads instead. Do not wake or
resume a stopped lead just to obtain a summary. Reuse a valid existing handoff;
request updates only for material staleness or lost context, with a finite timeout
and no repeated prompts while a request is pending. Missing/invalid handoff is a
visible limitation, not permission to invent scope or certify completion.

### F2 — Bounded observation interface and durable anchors

Owner: execute role for decided transport/CLI/store work after design approval.
Provide structured event metadata and public messages by default; represent tool
outputs by retrievable references and byte sizes, not recursively embedded bodies.
Fetch selected full outputs on demand with explicit pagination/coverage metadata.
Bound each response without silent truncation; an oversized single item must
remain retrievable through supported chunks or an explicit diagnostic. Never
advance coverage across unread required evidence or missing pages.
Persist handoff version, source anchors, pending evidence and assessed coverage
atomically. Keep transport receipt, message observation and evidence verification
as separate facts. Preserve active-turn updates and arrivals during an assessment;
handle invalid cursors, compacted history, restarts and unavailable references
without claiming a complete delta. Refresh a handoff only when justified; avoid
re-summarizing the entire session every tick. Retain exact task/binding fences,
private-reasoning exclusion, scoped access and secret-handling boundaries.

### F3 — Evidence-aware assessment and acceptance

Owner: lead for policy and verify role for consequential acceptance.
Compare handoff claims with original evidence when judging completion, diagnosing
contradictions or checking a relevant failure. A later success must retain an
unexplained earlier failure. Never promote target self-certification to verified
success. Record elapsed time, returned bytes and missing cost data honestly;
observe existing assessment/check allowances without new paid trials by default.

Deterministic CLI/protocol coverage must include large nested tool transcripts,
missing/stale handoffs, false completion in a handoff, omitted user corrections,
failure followed by success, stopped/read-only leads, duplicate handoff requests,
active-turn updates, pagination gaps, invalid cursors, unavailable evidence,
restart/compaction restoration and binding invalidation. Assert that unchanged
second checks do not replay historical output bodies and that all requested
original evidence remains accessible. Check message delivery counts to prove no
unauthorized or redundant summary requests. Run free checks before any separately
bounded native acceptance. Use an authorized long-session end-user path to measure
context volume and retained obligations; smaller payloads alone do not prove
semantic accuracy. Keep prior transport failures in the acceptance record.

### F4 — Integration, closure and rollback

Fresh milestone review precedes dependent policy/installation work. Reconcile the
skill policy, command contract and durable supervision documentation; run doc-end,
explicit doc-critic and separate final review before completion. Commit/release
remain separately authorized. Operational rollout must preserve existing task and
memory state and avoid concurrent overwrite of TEST-SUPERVISOR's repair.
Rollback disables the new summary/projection mode without deleting original
history or evidence; do not silently restore unbounded full-history model input.
If safe observation is unavailable, report incomplete coverage and retain a
resumption condition rather than retrying indefinitely.

### Skill instruction style — operator clarification

Use the compact, telegraphic English register used in inter-agent messages for
new or revised supervisor skill instructions. This is a writing convention, not
a new formal language or parser. Prefer explicit labels, short clauses, statuses,
evidence references and constraints; remove repeated explanations and connective
prose. Preserve readable spaces and separators: `cleanup=APPROVED; processes=156,
quiescent`, never `APPROVED156processes`.

Example instruction shape:

```text
READ: task + memory + delta.
CHECK: acceptance; evidence; unresolved failures; remaining allowance.
ACT: authorized scope only; one bounded intervention; verify follow-through.
VERIFY: delivery != compliance; target summary != independent proof.
SAVE: result; evidence; remaining; assessed cursor; coverage gaps.
STOP: verified completion | operator stop | indispensable blocker | actual limit.
```

Apply during F3 policy work, after the behavior contract is decided. Preserve
all authority boundaries, conditions, exceptions and failure handling; shorter
text alone is not acceptance. Review semantic equivalence against the original
rules and rerun the planned policy scenarios. No repository-wide skill rewrite
or immediate runtime change is authorized by this planning amendment.

### Priority correction — completion mandate drives execution

Operator correction, 2026-10-27: the TEST-SUPERVISOR trial demonstrated functioning
cron delivery but failed the intended behavior. Its task contained `Keep stopped
target stopped` and `No resumption of stopped original work`, so it repeatedly
observed an idle lead with unfinished work instead of driving completion. The
AI-KIT observation task was marked failed; timing passes do not erase this result.

Implement this correction before context-volume refinements:

- A completion mandate includes starting or waking the explicitly connected lead
  when authorized, feasible work remains. Native `idle`, a finished turn, and a
  historical stopped state are not operator pauses. Do not require another grant
  merely because the lead needs a new turn to execute its existing assignment.
- Reconcile prior stop instructions against the current supervisor mandate. A new
  explicit mandate to complete that same work supersedes an older execution stop;
  it does not erase scope, spending, release or other substantive constraints.
  Track an actual operator pause with its source, scope and subsequent resume.
  Respect current explicit operator instructions, including direct emergency stops;
  never infer pause from inactivity alone. Normal task pause/resume is managed
  through the supervisor, not duplicated as an unexplained permanent target ban.
- For an idle, incomplete, unpaused task with a feasible next step, send one bounded
  instruction to its root lead: unmet result, concrete next action, evidence to
  return, and checkpoint. Verify acknowledgement AND subsequent action. Delivery
  alone is insufficient. Avoid duplicate wake messages while an instruction is
  pending; distinguish legitimate waits, actual external blockers and repeated
  unproductive attempts. Do not implement an unconditional retry loop.
- If no authorized action is feasible, persist the specific blocker and resumption
  condition. Do not spend periodic model assessments merely confirming unchanged
  inactivity indefinitely; use an appropriate blocked/waiting schedule and notify
  the operator of lost coverage or the required external change.
- Keep supervisor turns bounded. Delegate authorized development/repair to an
  appropriate execution session; record ownership and checkpoint, then return to
  supervision. Waiting for development or review must not occupy the supervisor
  across scheduled checks. Do not silently grant repair or release authority.

Acceptance: a connected lead starts idle with an unfinished authorized task; the
supervisor wakes it without another user prompt, verifies real progress, resumes
it after an unjustified incomplete yield, and accepts completion only on evidence.
Controls cover initial idle, autonomous yield, current explicit pause, later resume,
older stop superseded by a completion mandate, real external blocker, pending
instruction deduplication and unchanged spending/release constraints. Verify that
long repair work is handed off and overdue checks remain visible. Deterministic
checks precede a bounded authorized real-session trial. Mere cron activity, quiet
idle workers or a timely assessment cannot satisfy this behavioral acceptance.

Update the existing brief/plan review scope for this correction rather than
restarting the project. This entry records planned work only; no implementation,
operational task modification or release is claimed by this amendment.

### Current scoped delivery — completion instruction correction

Scope: implement the brief's 2026-10-27 correction in SKILL.md and POLICY.md;
refresh installed copies, preserve all live tasks and unrelated WIP. Original
M0–M5 completion remains historical; context-volume features remain pending.
Sequence: fresh brief gate; fresh plan gate; edit entry/policy; independent
scenario/integration review; reconcile durable docs and active context; doc-end,
critic and separate final review; install reviewed instruction copies and verify
exact bytes/readability. No commit/release. Owner: AI-KIT lead. Reviewers: bounded
read-only gates, no operational messages or new sessions outside the review team.
Checks: skill validator, existing supervision install tests, mechanical gate,
scenario decisions with no native/business side effects. Rollback: restore only
backed-up instruction files; never alter tasks, cron or target sessions.

Instruction correction candidate: brief/plan/M1 reviews APPROVED; nine independent
model scenarios pass. Five actual temporary-HOME installer cases pass; skill
validator passes. Installed entry/policy match reviewed source bytes; existing
runtime asset bytes and cron unchanged. No live task migration or messages.
Documentation closure and separate final review pending; operational recovery
behavior remains unverified. Evidence: /tmp/ai-kit-supervisor-mandate/.

### Current addition — explicit end with individual stop confirmation

Owner: AI-KIT lead. Scope: CLI/control, native adapter, tests, skill/policy/command
docs and installation. Existing instruction correction is finalized separately.
Order: fresh brief and plan gates; implement durable end operation in existing
audit store, no schema migration; independent integration review; docs/critic,
separate final review; install verified assets. No release/commit or live end.
1. End begin: require exact binding/supervisor identity; detach/fence first.
   Persist operation identity and binding generation for retries. Remove owned
   cron only absent other active bindings. Inventory bound roots and verified
   descendants through supported native metadata. Incomplete inventory is visible.
2. End stop: consume explicit selected session IDs from per-session answers.
   Revalidate detached binding generation, membership and original active turn.
   Never interrupt a newer turn on stale approval. Record intent before mutation,
   verify status afterward; ambiguous sends reconcile without blind replay.
   No implicit worker stop approval. Report native queued work without deleting
   foreign submissions; remove only identifiable owned pending supervisor events.
3. Tests: actual CLI/protocol fixtures for no active targets, Yes/No, changed turn,
   shared cron, partial transport/cron failure, repeated end, reattachment fences,
   unknown/foreign IDs, queue ownership, worker ancestry and retained memory.
   Validate installed end help/skill and bounded native read/interrupt capabilities
   when available. Unknown native capabilities remain explicit, never fabricated.
Rollback: remove new command entry/restore backed-up assets; retain end audit,
detached state and stopped turns. Never restart targets as rollback.
