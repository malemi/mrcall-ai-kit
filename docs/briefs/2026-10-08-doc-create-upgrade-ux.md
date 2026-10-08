# Make documentation upgrades directly executable

## Intent

An explicitly requested documentation upgrade must work with the installed
helper, without asking the operator to produce client compatibility reports or
authorize each routine target-documentation correction. The v9.1.0 release made
runtime measurement a prerequisite for a deterministic file migration, then
added an escape flag requiring another authorization. That is the wrong default.

## Scope

- Make client compatibility evidence optional for layout migration. No report
  means compatibility is not evaluated, never that runtime support passed.
  An explicitly supplied report still receives strict validation. Preserve
  `--allow-unverified` as a backwards-compatible explicit deferral option.
- Keep ownership, recognized legacy bytes, staged mechanical validation,
  transactional publication and exact rollback. Do not hide mechanical errors.
- Make the installed doc-create workflow distinguish actionable target repairs
  from external prerequisite/ownership conflicts. An authorized upgrade includes
  repairing local metadata and links according to their actual meaning; only
  unresolved ownership, intent or external authority requires escalation.
- Retain efficient staging of application/child trees and structured mechanical
  diagnostics already present locally; verify their user-facing CLI path.
- Refresh kit-owned installed doc-create copies safely and update current docs.
  Preserve unrelated local completion-boundary work and its evidence.

## Acceptance

1. A recognized v8 disposable repository can inspect, dry-run, apply, pass the
   installed checker and roll back exactly using installed helpers, without a
   compatibility report, an escape flag, client launches or extra approval.
2. Supplied invalid/stale reports still refuse before writes. Foreign managed
   files and invalid target documentation still refuse without a transaction.
   Diagnostics name the correct bounded recovery; missing reports never route
   the default upgrade into runtime experiments.
3. Routine target repair is explicit in every installed supported doc-create
   workflow. Copies match source; foreign files/configuration are preserved.
4. No measured runtime compatibility or global agent compliance is claimed.
   Native matrices and broad suites remain deferred at the operator's request;
   focused deterministic CLI acceptance is retained with actual output.

## Delivery limits

No downstream repository migration, configuration changes or implicit release.
This is a repair under the current protocol, with separate publication authority.
The preceding migration-prerequisite experiment remains historical; its obsolete
mandatory acquisition direction is superseded by this brief, without fabricated
approval or native results.
