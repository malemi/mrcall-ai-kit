---
status: completed
brief: docs/briefs/2026-10-08-custom-claude-upgrade-consent.md
---

# Customized instruction adoption and resumable consent

## Ownership and dependencies

Lead owns doc-migrate.py, both doc-create workflow copies, focused upgrade CLI
acceptance, and directly affected migration documentation. Preserve concurrent
completion-boundary and compatibility-surface work. The brief is APPROVED;
implementation requires a fresh plan review. Release remains authorized after
this correction and excludes unrelated unfinished changes.

## M1 — Exact-file consent and recovery

- Add --adopt-claude-sha256 for inspect, dry-run and apply. Compare the supplied
  digest with the regular root CLAUDE.md snapshot before proposing any change.
  Reject absent/stale files and retain all version, path and sidecar checks.
- For a present custom/foreign file without adoption, return structured
  awaiting-authorization state, source hash and actionable preservation/consent
  guidance. Never mutate target files or create a transaction at this point.
- Record explicit adoption binding in the result and saved transaction.
  Preserve the original custom bytes/mode through existing exact rollback.
- Workflow reads both instruction files, prepares a concrete preservation
  mapping and requests consent. After consent, reconcile project rules outside
  managed content, retry all helper phases with the exact digest and verify.
  Never ask to delete blindly or treat permission waiting as task completion.
- Extend installed CLI fixtures for the full adoption/rollback path, stale hash,
  absent file, symlink and sidecar refusals. Preserve existing acceptance cases.
- Fresh M1 integration review before closure.

## Closure and verification

Update user-facing contract, current state and Unreleased notes. Use doc-end,
explicit doc-critic, current completion evidence, separate final review and
checker finalization. Native client trials and broad suites remain deferred;
focused installed CLI checks are required. No downstream repository edits.

## Rollback

Revert this task's local source edits independently. The managed transaction
restores the exact root instruction/profile preimages; project-prose transfer
is separately recorded and recovered. A changed custom source requires a new
proposal/consent rather than reusing an old digest.
