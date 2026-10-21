# Completion hook without a final answer

## Intent

Remove the reported global Stop failure `adapter error: missing final answer`
on ordinary turns. The v9.4.0 adapter validates the answer before checking whether
review applies; the actual hook CLI reproduces failure on an unarmed Stop without
`last_assistant_message`. Internal coordination is a possible trigger, not a
verified cause of all reported callbacks.

## Scope and constraints

Change only ai-kit completion admission order, deterministic regressions and
related documentation. No engine, cron, operational clone changes or restarts.
Preserve foreign work. No inference calls are needed. Keep strict declared
current-turn delivery, checked exec and exact-answer receipt validation intact.
No publication is included without current-task release authorization.

## Acceptance

- Actual installed hook CLI returns `{}` for unarmed Stop with absent, null,
  non-string or empty answer, including tracked tasks and repeated callbacks.
- Literal turn-bound `$nr` tolerates absent answer without certifying completion.
- Armed delivery and checked-exec callbacks still refuse absent/null answers;
  valid answers still require their current exact-answer receipt.
- Quiet callbacks create no challenge, attempts increment or successful audit.
- Focused protocol tests, installed copy/symlink CLI probes and mechanical check
  pass; affected docs state the measured limits. Refresh the installed adapter.

## Assumptions

The supplied message identifies this adapter; CLI reproduction establishes an
ordering defect, not the provenance of every real client event. Missing-answer
internal events need no invented user-visible final answer. Native session reload
and broader long-session behavior remain unverified.
