---
status: completed
---

# Reviewed delivery flow execution plan

Brief: [../briefs/2026-09-01-reviewed-delivery-flow.md](../briefs/2026-09-01-reviewed-delivery-flow.md)

## Review state

- Brief review: `APPROVED` after one `REVISE` cycle by independent reviewer
  `brief_review`.
- Plan review: `APPROVED` after two `REVISE` cycles by independent reviewer
  `plan_review`.

Every milestone gate below has the same transition rule: only `APPROVED` opens
the dependent milestone. `REVISE` blocks progression until its blocking
findings are repaired and the same milestone is re-reviewed. `BLOCKED` requires
the exact CTO decision or authority to be stated. A verdict is recorded in this
plan before dependent implementation begins.

## Milestone 1 — Canonical lifecycle and harness migration

- [x] Add the reviewed substantial-work lifecycle and strict fast path to the
  managed primary-agent contract.
- [x] Advance the documentation harness version and define the explicit
  migration from the preceding exact managed template.
- [x] Update shared commands, Codex workflow mirrors, checker expectations, and
  profile fixtures without weakening project-owned `AGENTS.md` boundaries.
- [x] Update the durable harness contract with stage ordering, review verdicts,
  milestone boundaries, and runtime fallback.

Verification:

- Managed template remains below 200 lines and matches repository `CLAUDE.md`
  byte-for-byte.
- Shared command files match Codex workflow mirrors.
- Checker tests prove v7 is rejected until explicit migration and v8 passes.
- An installed Codex or Claude `doc-create` flow migrates a disposable v7
  repository: project `AGENTS.md` remains byte-identical, only the exact managed
  `CLAUDE.md` is replaced, the profile advances last to v8, and the gate passes.
  A second disposable fixture with a modified v7 `CLAUDE.md` proves collision
  rejection with no repository mutation.

Review gate:

- A fresh reviewer checks the implementation diff against the approved brief,
  including brief-before-plan ordering, complete fast-path criteria, and
  migration ownership. Only `APPROVED` opens Milestone 2; `REVISE` is repaired
  and re-reviewed first.

Verdict: `APPROVED` by fresh reviewer `milestone1_review`. Evidence: 67 checker
tests passed; mirrors, managed template, whitespace check, and source-tree gate
passed; an installed Codex migration changed only the managed file and profile
version while preserving project instructions; the collision fixture remained
byte-identical before and after refusal.

## Milestone 2 — OpenCode lifecycle wiring

- [x] Update OpenCode orchestrator, build lead, plan mode, command, skill, and
  architecture so substantial work follows the reviewed lifecycle.
- [x] Extend the reviewer to judge briefs, plans, milestones, and final
  integration with the bounded verdict contract.
- [x] Grant `build` permission to invoke `reviewer`. Grant read-only `plan`
  permission to invoke `reviewer`; for substantial work it drafts and reviews
  brief text first, then drafts and reviews plan text, and returns both as a
  non-executing handoff. It never writes artifacts or begins implementation.
- [x] Preserve direct execution for strict fast-path work, positive-value
  delegation, proportionate verification, bounded fan-out, and CTO escalation
  limits.

Verification:

- Frontmatter permissions expose `reviewer` to orchestrator, build, and plan
  while plan remains read-only; prompt-contract tests require brief approval
  before plan mode may draft its plan handoff.
- Prompt-contract tests reject mandatory CTO approvals, default delegation,
  missing brief/plan gates, missing artifact-review coverage, and vague
  triviality language.
- Copy and symlink installs contain the same OpenCode lifecycle.

Review gate:

- A fresh reviewer checks OpenCode entry-point coverage, permission wiring,
  read-only plan handoff, verdict transitions, and fast-path consequences. Only
  `APPROVED` opens Milestone 3; `REVISE` is repaired and re-reviewed first.

Verdict: `APPROVED` by fresh reviewer `milestone2_review`. Evidence: OpenCode
frontmatter parsed, prompt-contract tests passed, copy and symlink installs
carried the lifecycle and reviewer permissions, orchestration install tests
passed, and the whitespace check was clean. The OpenCode executable is not
available locally; behavioral client coverage remains a Milestone 4 concern.

## Milestone 3 — Claude lifecycle wiring

- [x] Update the Claude router directive so substantial routed work follows the
  reviewed lifecycle before model delegation or implementation.
- [x] Extend the Claude judgment worker to review briefs, plans, milestones,
  and final integration with the bounded verdict contract.
- [x] Verify that the managed template supplies the same lifecycle when router
  mode is off and that router mode does not weaken it.
- [x] Preserve the direct trivial lane and session-memory behavior.

Verification:

- Real router-hook output contains strict fast-path criteria, sequential brief
  and plan review gates, and bounded verdicts.
- Claude worker installation exposes the artifact-review contract in copy and
  symlink modes.

Review gate:

- A fresh reviewer checks router-off and router-on instruction paths, worker
  role coverage, and absence of mandatory CTO approvals. Only `APPROVED` opens
  Milestone 4; `REVISE` is repaired and re-reviewed first.

Verdict: `APPROVED` by fresh reviewer `milestone3_review`. Evidence: the router
script compiled; its real emitted directive carried the complete lifecycle;
copy and symlink installs exposed the read-only artifact-review contract; all
router install, dormancy, injection, and session-path tests passed; and the
whitespace check was clean.

## Milestone 4 — Representative flows and documentation

- [x] Extend profile/install tests for both lanes and every shipped entry point.
- [x] Exercise a trivial real-client flow and a substantial real-client flow
  through installed artifacts where authentication and reviewer availability
  permit it.
- [x] Update living and durable docs with verified behavior and explicit
  runtime limitations.
- [x] Run repository shell and Python suites, mirror checks, `git diff --check`,
  semantic review, and the mechanical documentation gate.

Verification:

- Static tests prove contract distribution and permission wiring only; they do
  not claim behavioral enforcement.
- A real-client trace is required before claiming that a substantial agent does
  not implement before reviews. An unavailable client or reviewer remains
  explicitly unverified.
- The trivial real-client scenario reaches direct execution with one focused
  real check and no artifact/review ceremony.

Evidence:

- Claude Code 2.1.252 completed the disposable trivial flow in about ten seconds
  with no subagent or trace artifacts, and its one focused behavior check passed.
- A separate installed Claude flow changed a public CLI only after fresh Opus
  brief and plan approvals, then passed distinct milestone and final reviews;
  the final CLI behavior and installed documentation gate passed.
- A real installed Codex `doc-create` migrated an exact v7 fixture by changing
  only managed `CLAUDE.md` and the version field, preserving project instructions
  and passing the installed v8 gate. A modified v7 fixture was refused, with
  identical before/after SHA-256 manifests and a clean worktree.
- The Claude scope-guard adapter now handles streamed `MessageDisplay` fragments.
  An installed main-session `Edit` demonstrated one denial, visible reasoning,
  and one successful retry; all other matrix cells remain explicitly unverified.
- The Python checker and scope-guard suites, adapter tests, shell installer and
  profile suites, source/install mirror checks, template equality, Python and
  shell syntax checks, the source-tree documentation gate, and `git diff
  --check` pass. OpenCode is not installed, so its behavior has no client-level
  claim. The delegated semantic critic is clean with 57 claims verified.

Milestone review gate:

- A fresh reviewer checks test evidence, documentation truth, and any claimed
  client behavior. Only `APPROVED` completes Milestone 4; `REVISE` is repaired
  and re-reviewed first.

Verdict: `APPROVED` by fresh reviewer `milestone4_review`. Evidence: both real
Claude lanes, the installed Codex migration and byte-identical collision
refusal, the constrained Claude scope-guard retry, the complete green test and
install matrix, and the clean 57-claim semantic review satisfy the milestone;
OpenCode behavior remains explicitly unverified.

## Final integration review

After Milestone 4 is `APPROVED`, a different fresh review pass checks the full
integrated diff, all four recorded milestone verdicts, real-client evidence,
runtime limitations, documentation truth, and plan state. This is separate from
the Milestone 4 review. `status` changes to `completed` only after final
`APPROVED`; final `REVISE` findings are repaired and the integration review is
repeated.

Verdict: `APPROVED` by independent reviewer `final_integration_review` after
all four milestone verdicts were recorded. The integrated lifecycle, installed
client evidence, explicit runtime limitations, documentation truth, and work
trace are complete.
