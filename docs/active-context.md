---
doc_baseline_commit: b8665dccd95ff73c73048762b0af0f746169bf00
doc_baseline_date: 2026-08-31
---

# Active Context

<!-- doc-scope:start -->
Scope: Volatile snapshot of current verified state, unresolved work, and immediate next actions; never session history or durable design.
<!-- doc-scope:end -->

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Documentation harness v6 makes root `CLAUDE.md` a 12-line managed template that
imports project-owned `AGENTS.md`. Repository instructions, orientation, and
the thin-index budget now belong to `AGENTS.md`; the v5
`.claude/rules/doc-harness.md` sidecar and external `doc-index-scope` protocol
are obsolete. The checker enforces fixed ownership paths, exact template
equality, inline scopes, the 200-line project-index limit, and sidecar removal.

Installed Codex CLI flows verify fresh `doc-create`, explicit v5-to-v6
migration, scope-guard unmark during sidecar removal, and `doc-start`. The fresh
flow also proves that Codex loads a project-only probe from `AGENTS.md`. The
migration preserves the old v5 index byte-for-byte before adding its inline
scope. The Python suites, installer/mirror shell suites, and repository v6 gate
pass. A primary-session real-client run of Claude Code 2.1.251 returned the same
project-only probe through managed `CLAUDE.md`'s `@AGENTS.md` import after the
shell API key was unset, proving the loading chain once without claiming that
every authentication environment is currently healthy.

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
  environment-specific. The OpenCode executable is unavailable, so its loading
  path has no real-client proof.

## Next

- Repair or remove the stale Claude API-key configuration and normalize
  subscription login across execution environments. Install OpenCode before
  claiming its real-client path has been exercised.
- Complete the remaining scope-guard implementation plan, then run the installed
  clients through the same activation and write flows operators use.
- Record measured capability levels and limitations in
  [`scope-guard.md`](scope-guard.md) without promoting unit-test results to
  runtime proof.
