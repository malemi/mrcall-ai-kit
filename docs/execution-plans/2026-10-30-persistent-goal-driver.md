---
status: completed
---

# Persistent goal execution plan

## Approved input and ownership

Brief: [persistent goal execution](../briefs/2026-10-30-persistent-goal-driver.md).
Fresh brief reviewer `/root/persistent_goal_brief_review` approved SHA256
`a517915627af587c754cdc2b33cad253475f9bbf39821a878097243b7d946910`.
Read-only planner `/root/persistent_goal_plan` supplied this implementation design.
Independent verify `/root/goal_acceptance_design` supplied acceptance scenarios.
Retained evidence: `/tmp/mrcall-ai-kit/persistent-goal-20261030/`.

Lead owns integration, brief/plan, documentation and completion evidence.
Execute owns decided protected runtime and installation assets. Verify owns the
independent executable acceptance harness. Reviewer owns fresh lifecycle gates.
Workers receive explicit file ownership and bounded checkpoints; no worker may
revert existing dirty changes. Existing legacy supervision and live sessions stay
unchanged. No paid model experiment or live privileged deployment is required.

## Architecture

Deliver a distinct protected goal service alongside legacy observation-oriented
supervision. Reuse SQLite and existing native transport implementations without
migrating legacy task schemas or auto-enabling goals. Legacy pause/detach commands
must have no ability to stop this service or mutate its state. All state changes
use a narrow Unix socket API and authenticated Linux SO_PEERCRED.

Initial protected execution supports Codex targets. Its existing reconcile API
positively identifies the exact wake event in history with a completed turn.
Claude's existing adapter proves delivery but exposes no corresponding completed
turn predicate; protected goals reject that runtime explicitly. Legacy Claude
observation/supervision remains unchanged. This avoids pretending that receipt
or a generic idle observation proves consumption of the wake being reconciled.

The service's trusted code, configuration, database, acceptance bundles and
evidence are root-owned in protected paths. Only an operator UID (root in the
initial supported deployment) can create, stop, resume or change a goal. The
configured agent UID is non-root and distinct from the verifier UID. Agent
requests may inspect, report progress/obstacles or request acceptance, never
modify control state, contracts, limits or trusted results. Root/admin access
remains outside this protection; current mal sessions with unrestricted sudo
are not protected agents. Hardened setup diagnoses unsafe principals/paths rather
than silently downgrading to same-user protection.

The controller launches native adapter children as the native agent UID because
the existing adapter requires ownership of its native socket. It launches
candidate commands as agent UID and the independent checker as verifier UID.
Each child has cleared supplementary groups, no inherited control descriptors,
no_new_privs, a sanitized environment and bounded execution. Trusted controller
imports come only from the protected installed bundle/standard library; never
from agent-writable modules, Python startup hooks or working directories.

Operator control and admission are serialized with persisted generation fencing.
Long-running checks do not hold a database lock that prevents recording stop.
An admitted action may finish after stop, but its late result cannot override
the operator decision. No new action is admitted after the stop linearization
point. Resource boundaries are checked both at reservation and dispatch.

## Goal and acceptance contract

Persist goal identity, intent, scope, exact lead/supervisor IDs, native runtime,
immutable acceptance version, explicit limits, generation, next due time,
observations, attempts, dispatch IDs and append-only audit. Keep lifecycle and
attempt outcome separate: a blocked/failed report never changes an open goal.
Represent awaiting external input as a pending obligation rather than success.
Only verified acceptance, operator stop/pause or an explicit supported limit
ends automatic admission. Resume is explicit operator control.

The operator binds the reviewed acceptance bundle and declared dependencies,
interpreter, argv/environment and process timeouts before checking begins.
Snapshot candidate inputs into a retained immutable tree with a content manifest.
Refuse symlinks, unsafe replacement and unstable input reads. The result names
the exact snapshot and acceptance hashes, not merely a mutable worktree path.

Use a two-stage check: bounded candidate execution under the agent UID captures
actual output/exit/timeout metadata; the pinned verifier under its separate UID
judges that captured data and immutable inputs. Candidate code is never imported
or executed as root/controller or as the verifier. Checker success must have a
strict structured result and successful process exit. Reports from agents cannot
create acceptance receipts. Missing, changed or malformed evidence leaves the
goal open with a concrete diagnostic. Checker quality is a reviewed semantic
contract; runtime enforcement is not a proof of arbitrary human intent.

Supported initial operator limits are an absolute deadline and a wakeup budget,
plus explicit per-process bounds. Counters are reserved durably before admission.
No default failure-count cap or invented monetary/subscription accounting is
allowed. Reject unsupported budget fields rather than pretending to enforce them.
Failure diagnostics feed continuation, not blind replay of the failed command.

## M0 — Independent acceptance prerequisite

Before execute starts M1, the fresh plan reviewer must explicitly approve both
this plan and the independent verify contract retained at
`/tmp/mrcall-ai-kit/persistent-goal-20261030/acceptance-contract.md`.
That artifact records the actual verify handoff; the scenarios below incorporate
it into this plan. The lead retains its exact approved bytes and the review
verdict before implementation. This plan review is also the acceptance-design
gate; it is not postponed until implementation or test execution. Later changes
to acceptance semantics require independent verify justification and fresh
reviewer approval before relying on the revised check. Implementers cannot
weaken acceptance to make a candidate pass.

## M1 — Protected control plane

- Add protected store/service/client and explicit administrative setup assets.
- Implement strict configuration/input/schema checks, real peer authentication,
  lifecycle ownership, generation fences and read-only/report-only agent API.
- Protect files and ancestors (including replacement and symlink cases), child
  privilege separation and immutable trusted runtime. Setup remains dormant.
- Verify through copied installed assets, real sockets/subprocesses and separate
  restricted numeric UIDs under an isolated temporary root. No persistent OS user
  creation, live service activation, crontab change or host configuration change.
- Demonstrate agent denial for SQLite writes, stop/update, signal to controller,
  acceptance replacement and operator impersonation; demonstrate operator success,
  restart persistence, stale-generation rejection and unknown-command rejection.
- Fresh milestone review must approve M1 before dependent runtime work.

## M2 — Acceptance and M3 — Python continuation

- Bind reviewed acceptance before executing tests; implement immutable input
  snapshots, two-stage process execution, retained receipts and failure delivery.
- Implement periodic Python advance_goal: inspect actual native activity, follow
  busy work, directly resume unfinished idle leads, and wake idle supervisors
  with unresolved obligations independently of their willingness to intervene.
- Persist dispatch intent before sending. Reconcile uncertain/sending delivery
  across crashes and never blindly resend. Delivery is not consumption or task
  completion; require consumption/completed-turn evidence before another wake.
- Unknown native activity remains unknown; it does not authorize interruption.
  Repeated transport observation can recover without destroying the obligation.
- Serialize concurrent ticks, coalesce overdue cadence and keep empty ticks quiet.
  Admission uses current generation and remaining operator allowance.
- Native automated messages identify their provenance and preserved scope; they
  never present themselves as new operator authorization.
- Fresh combined milestone review precedes installation/documentation closure.

## Independent verification

Verify prepares and owns the executable cases independently of execute:

1. Installed service persists exact goal/limits/acceptance and failed attempt
   across restart; initial bad candidate fails, idle lead receives diagnostic,
   corrected candidate passes and only then closes with exact identities.
2. Lead idle and supervisor idle are separate cases. Busy/unknown activity never
   duplicates or interrupts work. A supervisor blocked/failed/completed report
   and a premature lead final answer cannot suppress continuation.
3. Native socket fixture accepts a send then drops its ACK; restart reconciles
   the original event ID, including delayed/ambiguous observations, without an
   additional send. Concurrent ticks have exact message-count assertions.
4. Stop/limit-change races fence new admission and late success. Each supported
   limit has a boundary case. Repeated failures below operator limits stay open.
5. Pinned checker/dependency replacement, symlink/ancestor substitution, malformed
   output, fake agent receipts and mutation during snapshot/check do not close.
6. Restricted children attempt protected-state/control/checker writes and signals.
   Candidate execution never inherits verifier/controller privileges.
7. Existing supervision store/scheduler/control/transport/runtime/installation
   suites remain green. Tests exercise actual CLI/service, not only functions.

The checker pins source snapshots and scripts; fixture transport demonstrates
runtime mechanics, not general model judgment. Paid live requests are unnecessary.

## M4 — Delivery and closure

Extend dormant installation to copy required goal assets with the supervision
feature and document the explicit administrative setup/service command. Refuse
unsafe runtime installations instead of silently running writable controller code.
Include operational create/status/report/check/stop/resume examples, accounting
limits, recovery, isolated acceptance and rollback instructions.

Lead reconciles docs/supervision.md, related installation overview, skill/command
routing and active context, preserving displaced historical text. Legacy
runtime-completion retirement remains unchanged. Run doc-end, mechanical/focused
completion checks, explicit doc-critic and separate final review; only then
finalize the declared plan transition. No release or live activation is included.

## Rollback and remaining work

Operator stops admission, shuts down the service and retains protected database,
snapshots and uncertain delivery records. Upgrade/rollback never converts an
uncertain submission to unsent or resets consumed allowance. Unsupported future
schemas are refused. Legacy supervision remains usable independently.

## Delivery evidence

M0 brief, plan and independent acceptance design are APPROVED. M1 protected
control plane and M2/M3 continuation/acceptance received separate milestone
APPROVED verdicts before dependent work. The M1 original gate's hashes remain;
a fresh M1 review covers the retained integrated source rather than reconstructing
an unavailable original approved body.

Independent verification runs the installed CLI/service and real Unix/native
protocol sockets under separate numeric UIDs. The 26-case suite passes, including
failed candidate → actual wake frames → corrected candidate → verified completion,
uncertain ACK/restart without duplicate delivery, stop/generation races, detached
child cleanup, source mutation and protected state denial. Receipt:
`/tmp/mrcall-ai-kit/persistent-goal-20261030/goal-admission-fence-independent-receipt.json`.
Earlier failures remain in that directory: detached child survival, mismatched
receipt identity, mutable candidate false completion and controller-death cleanup.
The stop-after-reservation case establishes that known unlaunched sends remain
not-delivered across resume while genuine uncertain sends remain pending.

M4 integrates dormant assets into the ordinary installer and documents protected
setup, operations, lifecycle ownership and limits. The completion task
`persistent-goal-driver-20261030` tracks installer/legacy evidence, semantic
documentation review and separate final-review readiness. Its declared active→completed
transition is reserved for successful finalization; no live deployment, root user
provisioning, PROBLEMI3 activation, paid model call or release is included.

