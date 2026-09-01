# Orchestration architecture

The OpenCode orchestration feature provides an autonomous primary engineering
lead plus optional workers and a risk-proportional reviewer.

## Entry points

- `agents/orchestrator.md`: default orchestration primary.
- `agents/build.md`: implementation-oriented primary using the same operating
  contract.
- `agents/plan.md`: read-only planning mode with proportionate depth.
- `commands/orchestrator.md`: launches the primary without approval ceremony.
- `skills/orchestrator/SKILL.md`: reusable orchestration policy.
- `agents/worker-*.md`: leaf executors with bounded scope and proportionate
  verification.
- `agents/reviewer.md`: optional review for consequential changes or evidence
  gaps, not a mandatory phase.
- `llms.md`: model metadata read only when selecting a worker.

## Control flow

```text
request
  -> inspect repository guidance and affected surface
  -> choose direct work or positive-value delegation
  -> implement and integrate
  -> verify in proportion to risk
  -> report outcome
```

Questions, delegation, reviewer use, and broad test suites are conditional
branches. They are not lifecycle gates.

## Delegation invariant

Coordination must have positive expected value. The lead keeps narrow,
reversible work. It delegates bounded substantive branches when parallelism,
specialist capability, or context isolation outweighs prompt construction,
waiting, and review.

Workers are leaf nodes. Their task prompt defines owned scope and non-goals.
They do not widen the task into repository audits or speculative refactors.

## Verification invariant

The changed behavior receives the smallest real check that can establish it.
Evidence expands with blast radius. Worker verification is reused unless the
lead needs integration coverage or has a concrete reason to doubt it; reviewer
verification closes evidence gaps rather than replaying a fixed checklist.

## Human interaction invariant

The user is the CTO, not an approval service for routine engineering decisions.
The lead escalates product ambiguity, material risk, irreversible action, or
missing authority. It owns implementation choices, recoverable failures, and
worker coordination.
