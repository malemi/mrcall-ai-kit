---
doc_baseline_commit: 3bf0173453327f7c9c3cf7579367e31f59b736da
doc_baseline_date: 2026-09-02
---

# Active Context

<!-- doc-scope:start -->
Scope: Volatile snapshot of current verified state, unresolved work, and immediate next actions; never session history or durable design.
<!-- doc-scope:end -->

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Documentation harness v8 makes root `CLAUDE.md` a managed template below 200
lines that imports project-owned `AGENTS.md`. It retains the autonomous
engineering-lead contract and adds two delivery lanes: a strict direct fast path
for local, obvious, reversible work with one focused real check, and independent
brief, plan, milestone, and final review gates for all substantial development.
Repository instructions, orientation, and the thin-index budget remain entirely
in `AGENTS.md`.

OpenCode's orchestrator, build lead, read-only planner, reviewer, command, and
orchestrator skill carry the same lifecycle. Build and plan may invoke the
reviewer; plan reviews brief text before drafting plan text and never writes or
implements. The Claude router emits the same gates when enabled, and the Opus
judgment worker reviews all four artifact kinds read-only. Direct implementation,
positive-value delegation, bounded fan-out, and proportionate verification
remain intact.

Static profile and installation tests cover every shipped entry point. Real
Claude Code 2.1.252 traces verify both lanes through installed artifacts: a
one-word local correction completed in about ten seconds with no subagent or
work trace, while a public CLI change ordered brief approval before plan
creation, plan approval before code, then separate milestone and final Opus
reviews. The final CLI behavior and v8 documentation gate passed.

The optional scope guard remains under the
[`scope-guard execution plan`](execution-plans/2026-08-26-scope-guard.md).
Claude Code's current `MessageDisplay` event carries indexed `delta` batches;
the adapter now assembles them through `final` before attesting. A real
main-session `Edit` in non-interactive mode verified one denial, a visible nonce
reason, and one successful retry. Other runtime and Claude interaction modes
remain unverified.

## Unresolved

- Scope-guard capability levels beyond Claude Code's main-session `-p` `Edit`,
  including interactive mode, `Write`, resume, subagents, and other runtimes,
  still require real-client verification.
- A routed session can still skip creation of its instructed session-memory
  file; the existing directive is not deterministic enforcement.
- The shell's `ANTHROPIC_API_KEY` takes precedence over the working Claude
  subscription login and leaves non-interactive requests at zero API tokens;
  removing that variable for the process restores normal client execution.
  The OpenCode executable is unavailable, so its new orchestration behavior has
  install-level but no real-client proof.
- Codex has no kit-installed global primary profile. Its doc workflows load the
  managed harness contract explicitly, while general sessions remain governed
  by Codex's user-owned global and project `AGENTS.md` chain.

## Next

- Remove the stale Claude API-key configuration at its owning shell-config
  source and install OpenCode before claiming its orchestration path has been
  exercised in the client.
- Complete the remaining scope-guard implementation plan, then run the installed
  clients through the same activation and write flows operators use.
- Record measured capability levels and limitations in
  [`scope-guard.md`](scope-guard.md) without promoting unit-test results to
  runtime proof.
