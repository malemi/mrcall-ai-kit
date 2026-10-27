# Large native history transport

## Intent and authority

The operator explicitly authorized transport repair in ai-kit on 2026-10-27,
verification against PROBLEMI2, deterministic large-history coverage, followed by
supervision activation with the existing limits and one real completed cycle.
The exact target is 01a1698a-21b3-7c53-8424-ae71e372339a in cs-kernel.

## Scope and constraints

Repair the native WebSocket receive ceiling in source and installed transport.
The observed response is 15,955,913 bytes; websockets defaults to 1 MiB.
Use an explicit finite 64 MiB ceiling, preserving deadlines, identity, paging,
reasoning exclusion and ambiguous-delivery semantics. Verify large reads and
reconciliation on a local protocol server, then a read-only actual target read.
Do not publish, commit unrelated work, restart daemons, run paid business tests,
increase budgets, or resume PROBLEMI2's stopped original work.
Preserve pre-existing working-tree changes. Keep the previous failure visible.

## Acceptance

- Deterministic protocol coverage passes above 1 MiB, including read and
  reconciliation, and explicitly refuses a response above the finite ceiling.
- Installed native transport reads PROBLEMI2 completely using pagination.
- Reconstruct original task, operator corrections, authorization and completion
  conditions from exchanges; bind the existing harness task when applicable.
- Observe the lead and established workers, verify parent chains, retain scoped
  memory, and install one real minute cron with at most 30 evaluations, each
  within 60 seconds. Verify at least one actual cron assessment to persisted
  execution-result before activation confirmation.
- Routine checks stay quiet. Interventions name missing result, next action and
  checkpoint; verify behavior after delivery. Alert on unconfirmed stop or real
  blockers. Notify status and explicit end of coverage before allowance ends.

## Assumptions

64 MiB covers the measured response, not arbitrary unbounded histories. Oversized
or incomplete observation remains a failure, never evidence of no problem.
Cron only dispatches while this supervisor is idle; activation must yield to a
real queued event to establish a full native cycle, not manufacture a receipt.
