# Reviewed delivery flow

**Date**: 2026-09-01 · **Plan**:
[../execution-plans/2026-09-01-reviewed-delivery-flow.md](../execution-plans/2026-09-01-reviewed-delivery-flow.md)

## Problem

Autonomy prevents the primary agent from burdening the CTO with routine
engineering choices, but autonomy alone does not impose enough structure on
substantial development. A large request can still move directly from intake
to implementation without an independently challenged brief, an independently
challenged plan, or review checkpoints while the implementation is still cheap
to correct.

The opposite failure is process without judgment: forcing a brief, plan, and
multiple reviews onto a tiny local change costs more than the work. The system
needs a deterministic substantial-work path and a deliberately narrow fast
path, while keeping both decisions owned by agents rather than turning them
into CTO approval gates.

## Decision

Substantial development follows this lifecycle:

1. The lead writes a brief covering intent, scope, constraints, acceptance
   criteria, and material assumptions.
2. A fresh reviewer checks the brief before planning. The lead resolves every
   blocking finding, revises the brief, and obtains a new verdict. Planning may
   not begin until the brief verdict is `APPROVED`; a justified `FAST_PATH`
   verdict skips planning and enters the direct path below.
3. The lead writes an execution plan with milestones, dependencies, ownership,
   verification, and rollback or risk handling where relevant.
4. A fresh reviewer checks the plan before implementation. The lead resolves
   every blocking finding, revises the plan, and obtains a new verdict.
5. The lead executes milestone by milestone. Every milestone receives an
   integration review before dependent work proceeds.
6. A final review checks the complete behavior through the final-user path and
   reconciles documentation and plan state.

Reviews are internal engineering gates, not requests for CTO approval. The lead
owns corrections and continues automatically. It escalates only a product
decision, material risk acceptance, irreversible or external action, or missing
authority that available evidence cannot resolve.

## Fast path

The lead may skip the artifact-and-review lifecycle only when all of these are
true:

- the change is local, obvious, and reversible;
- it does not alter a public contract, behavior boundary, persistent data,
  security posture, dependency graph, or migration path;
- it needs no decomposition or delegation;
- one focused real check can establish the result.

If the lead starts the structured path because scope is uncertain, the brief
reviewer may return a `FAST_PATH` verdict. The lead then skips planning and all
independent review gates, performs the direct change, runs its focused real
check, and reports. A plan reviewer may reach the same verdict when the plan
proves that the work meets every fast-path criterion; that verdict skips all
remaining milestone and final independent reviews and sends the work through
the same direct path. The reviewer must state which fast-path criteria are met;
"seems easy" is not sufficient evidence.

## Milestone boundary

A milestone is the smallest independently reviewable implementation unit that
delivers one acceptance criterion or changes one interface, persistent-data
shape, dependency, migration step, or externally observable behavior. A
milestone may not bundle independent changes merely to reduce review count.
The plan reviewer rejects an oversized milestone when part of it can be
implemented, verified, and corrected before dependent work begins.

Substantial work normally has at least two milestones. If it is genuinely one
indivisible implementation unit, it still receives an implementation review
before the separate final end-to-end review; the plan reviewer must confirm why
no earlier stable review boundary exists.

## Review contract

Where the runtime supports a fresh subagent, brief, plan, milestone, and final
reviews use an independent context. A runtime without that capability performs
an explicit separate review pass and reports the limitation; it does not omit
review silently.

Review verdicts are bounded:

- `APPROVED`: proceed to the next stage;
- `REVISE`: list blocking findings, which the lead fixes before re-review;
  non-blocking observations never halt the lifecycle;
- `FAST_PATH`: only at brief or plan review, with the satisfied criteria;
- `BLOCKED`: only when progress needs a genuine CTO decision or new authority.

Review reports stay concise and contain findings, evidence, and verdict rather
than reproducing the artifact.

## Acceptance

- Every shipped primary-agent path distinguishes the strict fast path from the
  reviewed substantial-work lifecycle.
- Substantial work cannot reach implementation before brief and plan reviews
  have passed.
- Planning cannot begin before the brief review returns `APPROVED`; a justified
  `FAST_PATH` verdict is the only exit from the structured lifecycle.
- Execution plans expose milestones and review gates; dependent work waits for
  the preceding milestone review.
- Plan review rejects milestones that bundle independently reviewable changes;
  a one-milestone substantial plan still has distinct implementation and final
  reviews.
- Reviewers can assess briefs and plans, not only finished code.
- Existing autonomy rules remain intact: internal review does not introduce CTO
  approval prompts or mandatory model-selection conversations.
- Mechanical tests reject profiles that omit the lifecycle, weaken the
  fast-path criteria, or describe review as universally mandatory for trivial
  work.
- Representative trivial and substantial flows are exercised through the
  installed artifacts or real clients wherever available, with runtime limits
  stated explicitly.
