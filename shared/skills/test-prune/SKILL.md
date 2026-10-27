---
name: test-prune
description: Audit and prune redundant or low-value tests while preserving distinct functional risks and recording decisions in repository memory. Use for requested test cleanup or consolidation, not routine test execution or making a failing suite green.
---

# Test pruning

Reduce maintenance cost without quietly discarding useful evidence. Judge a test
by the concrete failure it can expose, not its size, type or coverage percentage.
There is no target number of deletions. Keeping a justified test is a valid result.

## Scope and memory

Use the requested suite or component and its direct dependencies. If scope is
omitted, infer it from the active task; ask only when the ambiguity would change
what gets removed. A review-only request returns findings without editing tests
or creating repository records.

Follow the repository's existing lifecycle. With a compatible `docs/.doc-profile`,
apply `doc-start` before investigation, reusing valid orientation, and the required
reviews and `doc-end` for changes. Resolve skills from the current catalog and
applicable repository overrides. Reuse the active brief, plan and completion task
when this is part of that work; do not create a parallel approval process.
A missing or incompatible harness does not authorize bootstrap or migration.
If repository rules block work, report that condition rather than bypassing it.

For authorized cleanup with a compatible harness, keep the decision record in
`docs/test-audits/YYYY-MM-DD-<scope>.md`. Reuse the matching record when resuming;
avoid overwriting a different audit on the same date. Add a routing link in
`docs/README.md` on first use. Read relevant earlier audits and existing testing
guidance to recover rationale and unresolved failures, not unrelated histories.
Without a harness, use `scratch-test-prune-<scope>.md` in the repository.

The audit records:
- Scope, original test identities and source state sufficient to identify WIP.
- Keep/remove/consolidate decisions and concrete reasons. Group equivalent keep
  decisions when useful, but account for every test in an explicitly full audit.
- For each deletion, the surviving scenario and guarantee, or the precise check
  intentionally lost. Never claim equivalent coverage merely because tests pass.
- Actual commands, exit results, retained log/before-copy paths, review references
  and remaining uncertainties. Keep earlier failures and unresolved causes after
  later successes. Temporary paths are evidence locations, not durable guarantees;
  retain the decision and essential outcome in the repository audit.

## Decide before deleting

Read the test, its setup, the production path and existing functional evidence.
Ask what plausible user-visible regression it catches that surviving tests miss.
Good deletion candidates include repeated fake happy paths, assertions that merely
repeat a literal or implementation step, and validator matrices with no distinct
risk in the task. Those are candidates, not automatic deletion rules.

Preserve useful deterministic regressions: wrong targets, duplicate actions, lost
history, stale authority, concurrency, restart recovery and damage to foreign data
can matter even in small tests. A failing test needs diagnosis; failure alone is
never a reason to remove or weaken it. If the intended contract is unclear, retain
the case and record the unresolved decision instead of guessing.

Move unique guarantees into an existing meaningful CLI/API/protocol or lifecycle
scenario where that makes the evidence stronger. Establish the relevant precondition
independently: an earlier pause must not make a later detach assertion pass even
when detach is broken. Do not replace ten trivial tests with one giant trivial test.
Keep failure localization understandable. Prefer deleting redundant machinery to
adding helpers, mocks or a new framework for this cleanup.

## Edit, verify and close

Record deletion reasons before editing. Preserve unrelated WIP and exact before
bytes, including untracked tests. Keep task-created scripts, logs, reviews and
other temporary work artifacts; do not clean them up at the end.

Reuse valid baseline evidence. Choose the smallest real checks that can expose a
mistake in the removals or transfers; run the final affected suite when warranted.
Capture complete output and exit status, read the logs, diagnose failures and keep
failed evidence. Repeat checks only after relevant changes, failures or unresolved
acceptance justify it. Do not start paid/model trials when deterministic checks
suffice. Passing infrastructure tests does not prove model judgment or production
behavior outside the exercised path.

Reconcile affected coverage claims through the repository's normal closure.
Put reusable current testing guidance in its durable document, unresolved work in
the plan/current context, and detailed decisions in the audit. Keep active context
a current snapshot, not a test log. Report what was removed or retained and why,
the real verification result, intentional coverage losses and the audit/log paths.
