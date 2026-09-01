---
doc_baseline_commit: 4b3b263f78906da910a343fa122ec5da0926b552
doc_baseline_date: 2026-09-01
---

# Active Context

<!-- doc-scope:start -->
Scope: Volatile snapshot of current verified state, unresolved work, and immediate next actions; never session history or durable design.
<!-- doc-scope:end -->

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Documentation harness v7 makes root `CLAUDE.md` a 28-line managed template that
imports project-owned `AGENTS.md` and gives the user-facing agent an autonomous
engineering-lead contract. Routine reversible decisions stay with the agent;
delegation requires positive coordination value; investigation and verification
scale with risk and blast radius. Repository instructions, orientation, and the
thin-index budget remain entirely in `AGENTS.md`.

OpenCode's orchestrator, build lead, planner, optional reviewer, command, and
orchestrator skill follow the same contract. Mandatory model, strategy,
decomposition, and final-approval questions are gone; primary agents can edit
directly, reviewer use is conditional, repeated verification is rejected, and
parallel fan-out normally stops at three workers. All nineteen Claude/OpenCode
worker profiles carry a bounded-scope and proportional-verification contract.
The Claude router keeps narrow local work with its primary model and delegates
only when a fresh specialist context is worth prompting, waiting, and review.

The profile test exercises the router hook output and copy/symlink installs.
The verified client baseline is Claude Code 2.0.24 executing and checking a
focused one-line change directly through the v7 template in about fifteen
seconds, with no worker or broad suite. The checker Python suite,
installer/mirror shell suites, and repository v7 gate pass.

The optional scope guard remains under the
[`scope-guard execution plan`](execution-plans/2026-08-26-scope-guard.md). Its
runtime adapters are still unverified and are not described as working.

## Unresolved

- Scope-guard capability levels, event ordering, subagent behavior, and bypasses
  still require real-client verification in all three runtimes.
- A routed session can still skip creation of its instructed session-memory
  file; the existing directive is not deterministic enforcement.
- With the shell's `ANTHROPIC_API_KEY` set, non-interactive Claude prompts time
  out. Subscription auth succeeded in the primary session but an independent
  critic environment reported `Not logged in`; `claude doctor` separately
  reports HTTP 401 for remote managed settings. Authentication availability is
  environment-specific. The OpenCode executable is unavailable, so the new
  orchestration behavior has install-level but no real-client proof.
- Codex has no kit-installed global primary profile. Its doc workflows load the
  managed harness contract explicitly, while general sessions remain governed
  by Codex's user-owned global and project `AGENTS.md` chain.

## Next

- Repair or remove the stale Claude API-key configuration and normalize
  subscription login across execution environments. Install OpenCode before
  claiming the new orchestration path has been exercised in the client.
- Complete the remaining scope-guard implementation plan, then run the installed
  clients through the same activation and write flows operators use.
- Record measured capability levels and limitations in
  [`scope-guard.md`](scope-guard.md) without promoting unit-test results to
  runtime proof.
