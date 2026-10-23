---
status: completed
---

# Failed execution-plan status

## Approved scope

Implement the [brief](../briefs/2026-10-23-failed-plan-status.md): `failed` is a
terminal unsuccessful plan outcome, distinct from suspended work and successful
completion. Existing plans and unrelated automatic-av work remain untouched.

## M1 — Implementation and real CLI verification

Lead owns `shared/scripts/doc-check.py`, its CLI regression suite, shared
doc-create/doc-end workflows and identical Codex WORKFLOW copies, plus the plan
state paragraph in `docs/documentation-harness.md`.

1. Accept `failed` in plan validation and exclude it from startup's open plans.
   Preserve malformed/duplicate/unknown-status visibility and other state types.
2. Document the six states and require failed plans to retain the unmet result
   and failure reason. Failed is never successful completion; the completion
   evidence finalizer keeps its existing active-to-completed restriction.
3. Extend actual checker CLI fixtures to cover failed acceptance, terminal/open
   startup distinctions and invalid-status refusal. Run checker and evidence
   regression suites plus cross-client workflow equality checks.
4. Obtain fresh M1 review of the source and actual CLI results before closure.

## Documentation and final integration

Lead reconciles only affected contracts and this work trace. Existing active
context and automatic-av plan remain unchanged. Invoke doc-end and doc-critic,
including the unchanged active-context shape and unchanged AGENTS contract.
Record scoped completion evidence, obtain a separate fresh final review, then
use checker finalization for the declared plan transition. No installation,
global settings, commit, release, paid inference or service restart.

## Dependencies and rollback

No new dependency. Shared workflows deliver to Claude/OpenCode commands; Codex
ships matching copies. Existing installed copies require a later explicit
refresh. Roll back only this task's hunks and new trace pair; preserve all prior
working-tree bytes, including other hunks in documentation-harness.md.

## Completion transition

Keep status active until the checker finalizes the reviewed active-to-completed
transition. Required evidence: real checker CLI acceptance/startup/refusal,
focused regression, mechanical gate, critic, M1 and separate final approval.
