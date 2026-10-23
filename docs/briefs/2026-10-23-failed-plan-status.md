# Failed execution-plan status

## Intent

Represent a concluded unsuccessful attempt explicitly, without reporting it as
completed or keeping it among work that is merely waiting to resume.

## Scope and constraints

Add `failed` to the shared execution-plan status contract, mechanical validation,
startup reporting, and creation/closure workflows for all supported clients.
It is a terminal unsuccessful outcome, distinct from resumable `blocked` and
successful `completed`. Record the unmet result and reason in the plan.
Do not relabel existing plans, change session/issue states, weaken completion
evidence, or modify the unrelated automatic-av candidate. No release or global
installation is requested.

## Acceptance

- The actual checker CLI accepts plans with `status: failed`.
- Startup omits failed plans from `open_plans`, while retaining planned, active,
  blocked and unknown states as before.
- Invalid status values still fail validation.
- Shared workflows and their client entry points agree on the six valid states
  and explain that failed is unsuccessful, not verified delivery.
- Focused regression and real CLI fixtures pass without model inference.

## Assumptions

`failed` closes an unsuccessful attempt; remaining desired work requires a
recorded next decision, rather than being silently declared completed. Existing
completion finalization remains restricted to successful `active` to `completed`.
