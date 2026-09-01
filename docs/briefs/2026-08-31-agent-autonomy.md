# Agent autonomy and proportional effort

**Date**: 2026-08-31 · **Plan**:
[../execution-plans/2026-08-31-agent-autonomy.md](../execution-plans/2026-08-31-agent-autonomy.md)

## Problem

The kit's agents can optimize for local thoroughness while making the operator
slower. They may interrupt for implementation-level choices they can resolve,
delegate work whose coordination costs more than doing it directly, or run a
broad verification campaign for a tiny and reversible change. That behavior is
technically cautious but operationally poor: it transfers thinking and waiting
back to the human who asked the agent to remove them.

The primary agent needs to behave like an accountable engineering lead who
reports to a CTO. Workers need the same sense of proportion, but a different
interface: stay inside the assigned task, produce useful evidence quickly, and
avoid expanding a narrow change into an unsolicited audit.

## Decision

Define one delivery contract with role-specific application:

- Optimize for the CTO's elapsed time and attention, not for displaying effort.
- Solve routine technical uncertainty independently. Escalate only a material
  product, risk, authority, or irreversible choice that cannot be resolved from
  repository evidence.
- Match process to consequence. Small, local, reversible edits are performed
  directly and receive a focused verification; broader or risky changes earn a
  plan, delegation, and wider tests.
- Delegate only when parallelism, specialist knowledge, or context isolation is
  worth more than coordination and waiting. A trivial edit is not a worker task.
- Keep workers bounded: no speculative refactors, broad repository audits, or
  full-suite testing unless the change's blast radius justifies them or the
  parent explicitly requests them.
- Report outcomes, material tradeoffs, and genuine blockers. Do not interrupt
  merely to narrate competence or push an implementation decision upward.

The contract must be concise enough to survive in agent context and must have a
single maintained source where the adapters permit one. Runtime-specific files
may add mechanics, but must not redefine the operating philosophy independently.

## Acceptance

- Every user-facing primary-agent path shipped by the kit receives the autonomy
  and CTO-interface contract at the point it can actually influence behavior.
- Every shipped worker profile receives proportional-scope and verification
  guidance.
- Delegation instructions explicitly reject low-return delegation and require a
  bounded task with a useful expected payoff.
- Tiny-change scenarios lead to direct execution plus focused verification in
  real or representative client flows; substantial work still preserves the
  existing correctness and end-to-end verification rules.
- Documentation identifies unavoidable runtime limits instead of claiming a
  universal primary-agent profile where the platform exposes none.
