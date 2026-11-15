# Persistent goal execution

## Intent

Keep an explicitly authorized assignment moving until verified acceptance,
operator stop, or an operator-configured limit. PROBLEMI3 exposed a concrete
failure: the supervisor converted a recoverable adoption failure into a terminal
supervision block. Instructions to persist did not prevent that transition.
The operator requested Python-owned continuation, including correction of idle
leads and supervisors, rather than another prompt-only instruction.

## Scope

Extend AI-KIT's persistent supervision with a durable goal and an external Python
driver. Reuse SQLite, transport and scheduling mechanisms where suitable. A goal
contains the intended result, exact target, authorized scope, acceptance contract,
operator limits and persistent attempt history. Failed/blocked assessments and
ordinary final answers cannot close or suspend it. The driver follows running
work, reconciles uncertain delivery, resumes unfinished idle work, and retains
the next obligation across restart. It does not rerun a known failed operation
blindly: diagnostics go back to the lead for the appropriate next action.

Acceptance is prepared independently of implementation by verify from the brief,
reviewed by reviewer, and bound before execution. The runner executes the bound
check and records its actual result. An agent's success assertion is insufficient.
Debugger is used for uncertain causal diagnosis, not automatically for new work.
Executable acceptance must be bounded and authorized for its real environment;
the goal mechanism must not execute arbitrary unreviewed commands or test bodies
changed by the implementer as trusted acceptance.

Stop, cancellation, changes to limits, acceptance and scope belong to the
operator control plane. Agent-facing reporting cannot exercise those operations.
The implementation must offer an enforceable process/permission boundary, not a
self-asserted `actor=operator` field or an agent-readable secret. The current
same-user unrestricted shell cannot authenticate a human against an agent with
identical privileges. Protected operation therefore requires separated OS
principals or equivalent sandbox enforcement; it must diagnose an unmet boundary
and must never advertise same-user mode as tamper-proof. This is a deployment
prerequisite to implement and verify, not a claim about the current live sessions.

## Constraints

- Preserve existing observation-only tasks and historical state; no automatic
  conversion or resumption of stopped sessions, including PROBLEMI3.
- Do not install into the live host, change live cron, privileges or supervision
  bindings, publish, release, or commit unrelated dirty work as part of development.
  Deliver installation/support paths and verify in isolated environments.
- Preserve operator scope, authority, required reviews and resource limits.
  Continuation is not permission to bypass a genuinely missing authorization.
  Such an obstacle remains a pending obligation; independent authorized work
  continues and operator input resumes dependent work without losing the goal.
- Do not infer subscription credit or dollars from turn counts. Enforce supported
  explicit limits before admission and expose unsupported/unknown accounting.
  No paid model calls are needed for acceptance of runtime mechanics.
- Conserve tokens: bounded role handoffs, existing evidence reuse, deterministic
  tests and quiet no-work ticks. No broad model matrix or speculative refactor.
- Native transport failures and unavailable/ambiguous activity are diagnosed,
  reconciled and retained; they are not success or permission for duplicate sends.

## Acceptance

1. A goal and its exact acceptance/limits survive process restart. Ordinary
   assessment results, stale callers, pause/fail/block/complete commands and
   detach/deactivation paths cannot bypass protected goal ownership.
2. An unfinished idle lead is resumed by Python without depending on a supervisor
   choosing to intervene. An idle supervisor with an unresolved obligation is
   resumed; busy work is not duplicated or interrupted just to satisfy a timer.
3. A real bound executable check fails, its failure reaches the continuation
   path, a subsequent corrected candidate passes, and only then the goal closes.
   Changed acceptance artifacts, spoofed receipts and malformed results cannot
   establish success. A passing check's exact candidate/evidence is retained.
4. Operator stop and configured limits prevent new admission. No invented
   failure-count cap stops an otherwise authorized goal. Uncertain outstanding
   sends are reconciled before more work; stop/limit races are covered.
5. The agent control surface cannot stop/change a goal or write protected state;
   an isolated real OS-permission exercise establishes the stated boundary.
   Plain same-UID access is explicitly outside that security claim.
6. The installed CLI/service path is exercised in an isolated environment, with
   real subprocesses, SQLite recovery and representative native transport fixture
   behavior. Existing supervision, installation and observation-only contracts
   continue to pass. Native semantic judgment is not inferred from fixtures.
7. Required lifecycle reviews, documentation reconciliation, doc-critic and
   separate final review are complete with current evidence and honest limits.

## Assumptions

The user authorized implementation, not a live restart of supervision. Existing
operator policies remain valid; the earlier weekly-credit stop was explicitly
removed. Python enforces lifecycle/admission and executable acceptance; it cannot
prove that an arbitrary acceptance program exhaustively captures human intent.
Reviewer independence and a precise acceptance contract remain necessary.
