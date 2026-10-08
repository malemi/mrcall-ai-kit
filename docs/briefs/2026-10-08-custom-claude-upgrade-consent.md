# Resolve customized instructions during an authorized upgrade

## Intent

A customized CLAUDE.md must lead to a concrete preservation proposal and an
operator authorization question, never a terminal refusal without recovery.
The operator explicitly requests this correction before the authorized release.

## Scope

Add a hash-bound, explicit adoption option to the installed migration helper.
Without consent it preserves customized content and returns structured approval
instructions. After the operator approves a concrete mapping of project rules
into AGENTS.md, the workflow reconciles those rules and uses the exact observed
CLAUDE hash for inspect, dry-run and apply. The existing transaction retains the
original custom bytes and mode and restores them on rollback. No automatic
semantic merge, blanket deletion permission or weakened path checks.

Make every installed doc-create workflow ask the specific unresolved question
and remain ready to continue after the answer. Distinguish waiting for approval
from a completed refused task. Preserve routine repair and optional report UX.

## Acceptance

- Default customized-file inspection writes nothing and returns an actionable
  approval request with the exact source hash.
- Exact authorized adoption completes installed CLI inspect/dry-run/apply/check
  and exact rollback; transferred project rules survive in AGENTS.md.
- Wrong/stale hashes, symlinks and unrelated collisions still refuse without
  writes. A custom-file consent cannot authorize other instruction files.
- Workflows explain the concrete proposal, approval and resumption, and retain
  separate recovery boundaries for project-prose reconciliation.

## Limits

No downstream repository migration in this kit task. Native client experiments
and broad regressions remain deferred under the existing operator instruction.
Focused installed CLI acceptance is required. Release follows this correction
under the operator's existing explicit authorization, excluding concurrent work.
