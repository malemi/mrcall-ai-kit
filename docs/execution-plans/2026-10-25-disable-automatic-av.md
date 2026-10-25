---
status: completed
---

# Disable automatic av installation

## Approved scope

Follow the [brief](../briefs/2026-10-25-disable-automatic-av.md). Publish a patch
that leaves automatic av off on fresh installs and upgrades, preserving manual
av and unrelated configuration. No operational clones or session restarts.

## M1 — Installer and real installation evidence

An execute worker owns install.sh and tests/test_auto_av_install.py only, with a
240-second candidate deadline. Remove plugin bundle/dependency installation and
use existing ownership-aware off operations for selected runtimes; retain safe
legacy retirement and foreign-file protections. Preserve unrelated roles.
Update actual isolated-home installer tests for fresh and seeded-owned upgrades,
copy/symlink, repeat installation, foreign plugin/registry preservation, manual
av and no npm. Lead runs focused checks and independent integration review.

## Closure and delivery

Lead owns current README, runtime contracts and active-context reconciliation,
changelog, evidence and release. Historical plans/briefs retain original scope.
Run doc-end, mechanical gate, scoped independent doc-critic and separate final
review. Checker finalizes baseline and active-to-completed only after approval.
Commit explicit owned paths, run the ordinary installer on the host, verify
zero registrations/manual av, then publish through the authorized release flow.
Full free release tests are required; no paid model acceptance.

## Rollback

Restore only task-owned installer/docs changes or owned registry backups.
Never reactivate automation without explicit authorization; preserve foreign
hooks, credentials, historical evidence and manual av. Loaded sessions retain
the documented native reload boundary.
