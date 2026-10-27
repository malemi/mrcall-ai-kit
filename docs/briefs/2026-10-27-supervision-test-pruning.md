# Prune low-value supervision tests

## Intent

The operator requests removal of useless tests and a scratch file explaining each
removal. The preceding discussion concerns the supervision suite. Test value is
the concrete failure it can reveal, not assertion count or coverage percentage.

## Scope and constraints

Audit every case in `tests/test_supervision_*.py`. Remove duplicate scenarios and
implementation-mirroring checks with no distinct operational risk. Consolidate
valuable assertions into existing CLI/protocol scenarios where a separate fake
transport or database-only case adds no evidence. Do not delete tests merely for
being deterministic or small: retain regressions for duplicate delivery, lost
history, stale authority, wrong targets, caps stopping useful work, broken cron
and damage to foreign installation assets.

Keep production code, installed assets, native sessions and existing WIP unchanged.
Do not run paid model trials. Do not alter TEST-SUPERVISOR2 or TEST-SUPERVISOR3.
No commit or release. Preserve before-test bytes outside the checkout because the
supervision files are existing untracked WIP.

## Acceptance

- Every original supervision test has an explicit keep, remove or consolidate
  decision in `scratch-supervision-test-pruning.md`.
- Each removal explains its low value and surviving coverage, or explicitly names
  a narrow check intentionally dropped. No vague claim that all unit tests lack value.
- Useful unique behavioral assertions survive in meaningful scenarios. No numerical
  reduction target and no unsupported claim of equivalent full coverage.
- Run the final reduced suite once, retaining verbose logs and inspecting failures.
  Existing CLI/protocol/installer cases exercise actual commands without model calls.
- Document that infrastructure checks do not establish supervisory judgment.

## Assumptions

This task prunes the supervision tests discussed in the conversation. Unrelated
repository test suites and a redesign of the completion-evidence system are outside
scope. The scratch file is an auditable rationale, not a new testing framework.
