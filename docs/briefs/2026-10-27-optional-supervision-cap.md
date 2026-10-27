# Completion-driven supervision without a default check cap

## Intent

The operator entrusts the supervisor with driving connected sessions to verified
results. The clock checks progress; elapsed time alone must not terminate useful
work. The earlier 30-check trial stopped unfinished. Its failure and unresolved
causes remain evidence even after subsequent successes.

## Scope and constraints

- Omitted or null `limits.max_checks` means no count cap; explicit positive
  integers remain binding. Existing finite values are not migrated implicitly.
- Remove invented reviewer/worker deadlines. Assess progress, repetition, blockers
  and scope drift. A long operation alone is not a blocker.
- Wake an idle lead with a concrete authorized next action when acceptance is unmet.
- Distinguish transport timeouts, assessment checkpoints and operator limits.
  Technical uncertainty requires reconciliation; checkpoints require reassessment;
  neither independently authorizes abandoning an incomplete assignment.
- Preserve audit, execution history, unresolved causes, scope and spending rules.
- Preserve all WIP. Do not alter, reactivate or send input to TEST-SUPERVISOR2.
- Install locally after deterministic verification and review. Use a NEW supervisor
  session for the next native trial, with its mandate and effective configuration
  stated before creation. Do not launch paid acceptance where deterministic checks
  suffice. No commits, release, daemon restart or unrelated target changes.

## Acceptance

1. Actual CLI creates uncapped tasks by omission/null and rereads null.
2. Scheduler continues beyond the former default; explicit and legacy caps bind.
3. Invalid non-null caps fail; updates retain history and invalidate old executions.
4. One-shot semantics and transport recovery remain sound. Checkpoint expiry does
   not discard a useful active assessment or exhaust an implicit lifetime reserve.
5. Skill, policy, commands and durable docs consistently describe these distinctions,
   idle-lead intervention and retention of earlier failures.
6. Installed bytes and installed CLI behavior verified. TEST-SUPERVISOR2 untouched.
   Deterministic native-protocol fixtures prove routing and state behavior separately
   from model judgment. Any new real supervisor session has a recorded mandate,
   configuration, exact identity and evidence boundaries; no inferred behavioral pass.

## Assumptions and correction

No count cap grants no unlimited spending authority. Actual resource exhaustion,
operator pause/cancel and legitimate blockers retain unfinished obligations.
The operator's 2026-10-27 correction supersedes the previously approved instruction
to restore TEST-SUPERVISOR2. That restoration must not be performed.
