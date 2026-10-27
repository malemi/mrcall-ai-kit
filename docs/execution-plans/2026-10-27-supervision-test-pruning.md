---
status: completed
---
# Prune low-value supervision tests

Brief: ../briefs/2026-10-27-supervision-test-pruning.md
Audit and deletion rationale: ../../scratch-supervision-test-pruning.md
Evidence root: `/tmp/supervision-test-pruning-20261027/`.

## Ownership and dependencies

Lead owns the audit, edits and final verification. Fresh reviewers own brief,
plan, milestone and final gates; doc-critic remains separate. Preserve all WIP.
Brief approved; immutable approved artifact and raw verdict are in the evidence root.

## M1 — Prune and consolidate

After plan approval, implement the ten named removals in the scratch ledger.
No runtime change. Modify only the five affected supervision test files:
control, cron, scheduler, store and transport. Keep install, harness and runtime
cases unchanged. Move useful event-collision/delivery assertions into the real
CLI/Unix-socket scenario; submit its result via CLI. Add pause/detach coverage to
the existing CLI refusal case. Move two-task exclusion into busy/restart dispatch,
and same-event recovery plus restored failure memory into the recovery scenario.
Retain transport receipt and no-extra-start guarantees in existing CLI/lost-ack
cases. Trim only the two low-value assertion groups named in the audit.

Use the saved before inventory to account for every removed method and preserve
unchanged tests. Inspect the diff against saved WIP, not only HEAD (these files
are untracked). Preserve before bytes for exact local rollback. Finalize scratch
rationales and update only current test-coverage claims in docs/supervision.md;
leave historical native measurements intact. Finish all content before the one
final reduced-suite run, retaining verbose stdout/stderr and its exit status.
Use existing actual CLI/protocol/installer paths; no paid native trial. Repair
failures and repeat only affected checks when new evidence warrants it.
Obtain an independent milestone review of deletion justification and retained risks.

## Closure

Run doc-end with affected scope: brief, plan, scratch ledger, supervision contract
and active-context shape (unchanged). No installed artifact changes, commit or
release. Final review compares approved brief/plan/test source, actual command
results, scratch inventory and intentionally dropped checks. Use checker
finalization for the active-to-completed transition only after approval.

## Verification and rollback

Configured startup build is clean. Reuse the previous unchanged 62-case run as
baseline evidence; no redundant baseline rerun. The final command is
`python3 -m unittest discover -s tests -p 'test_supervision_*.py' -v`.
A saved before-manifest and per-method inventory identify deletions. Rollback
restores only changed test/doc files from this task's before copies, preserving
all other WIP. Failed logs remain alongside successful results.
