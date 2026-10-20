# Execute the completion check at the runtime boundary

## Intent

The operator repeatedly requested that agents check whether the whole assignment
is finished before concluding. The shipped mandate-completion text and optional
Codex reread skill remain instructions that can be skipped. Passing instruction
fixtures did not deliver an automatically executed completion check.

Connect Codex's native Stop boundary to an observable completion check. A normal
terminal attempt must invoke the runtime check even when the model ignores the
kit instructions. A missing required review/result must produce a continuation
or an explicitly failed/limited terminal outcome, never an implicit successful
pass merely because a previous Stop already fired.

## Scope and constraints

Work only in ai-kit and owned hook installation assets. Preserve foreign hooks,
operator text, unrelated WIP and existing completion evidence. Do not change the
Codex engine, cron, downstream repository protocols, or restart other sessions.
Do not infer semantic completion with regex or string heuristics. Reuse the
existing mandate rules and task-bound completion checker when an explicit task
binding is available; do not guess a task from repository recency.

A runtime-invoked check and a recorded model review are distinct from proof that
the model's judgment is true. Scope the guarantee to the actual trusted and
activated hook path. Stop continuation may create a new prompt after the draft
is visible; do not claim the host can retract or withhold that draft without
native evidence. Preserve pauses, cancellations, questions and legitimate
input/authority/resource stops. Bound retries, elapsed time and paid acceptance;
never auto-allow a missing required check at the retry cap.

## Acceptance

- Demonstrate actual Codex 0.163.0 Stop delivery and continuation semantics using
  the installed CLI/app-server in an isolated setup. Prefer a deterministic local
  provider for transport tests, without paid inference or production changes.
- Automatically execute the check on terminal attempts; retain an owned receipt
  identifying the runtime/session, attempted result and actual decision. Require
  current review evidence where applicable, including after a skipped first pass.
- A deliberate attempt to finish without the required check must not silently
  pass. A repeated attempt must remain refused or surface a concrete bounded
  failure. Completed work and legitimate limited stops must have tested paths.
- Registration, status and removal preserve other hooks and distinguish installed,
  registered, trusted and actually observed execution. Prepare a concrete validated
  result before any operator trust/activation step; never fabricate trust or edit
  its internal store. Complete client-path proof is required before claiming live
  enforcement, and missing indispensable activation is an explicit obligation.
- Cover fresh turns, continuation, stale/cross-session receipts, malformed inputs,
  retry limits and applicable explicit completion-record bindings deterministically.
  Run meaningful installed-path checks. Buy a native model conversation only if
  deterministic transport tests cannot establish a required fact, at most one
  initially, with timeout and output limits and a recorded reason before spending.
- Follow brief/plan/milestone reviews, documentation closure and a separate final
  review. Commit checked changes. Publication is not part of this correction.

## Technical evidence and unknowns

The installed CLI is Codex 0.163.0 with hooks enabled. Official hook documentation
lists Stop, a continuation decision, turn identity and stop_hook_active. The kit
currently registers only PreToolUse for Codex scope guard. Actual Stop invocation,
continuation identity, trust behavior and any second-pass suppression must be
measured before choosing the enforcement design.
