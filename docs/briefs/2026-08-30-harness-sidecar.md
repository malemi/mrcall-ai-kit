# Harness-owned entry point, project-owned instructions

**Date**: 2026-08-30 · **Plan**:
[../execution-plans/2026-08-30-harness-sidecar.md](../execution-plans/2026-08-30-harness-sidecar.md)

## Problem

Harness v5 fixed the 207-line deadlock by moving protocol text from the
configured index into `.claude/rules/doc-harness.md`. The mechanics work, but
the ownership model is inverted. In this system `CLAUDE.md` is supplied by the
harness: changing harness behavior belongs in its versioned template and should
reach repositories through an explicit migration. Repository-specific guidance
is what needs a separate committed file.

Calling the generated sidecar "harness-owned" also mixes two different things:
the global protocol and one repository's index scope. It solves a line count
without establishing a clean source of truth.

## Decision

Harness v6 makes ownership visible in the filenames and loading chain.

- `harness_file = CLAUDE.md`. The root file is an exact managed artifact rendered
  from the installed harness template. It contains the generic harness protocol
  and imports `AGENTS.md`; repositories do not add local guidance to it.
- `index_file = AGENTS.md`. This is the committed, project-owned thin index with
  the 200-line budget, repository orientation, ownership, commands, conventions,
  and links to durable docs.
- Claude Code reads `AGENTS.md` through the template's `@AGENTS.md` import. Codex
  and current OpenCode discover root `AGENTS.md` natively. `doc-start` still reads
  both configured files explicitly when the active runtime has not confirmed
  them in context.
- Both configured files carry their own inline scope. The v5 external
  `doc-index-scope` protocol and its scope-guard lookup disappear.
- The canonical `CLAUDE.md` template is installed beside the checker and used by
  `doc-create`, the gate, and migrations. A template change requires a harness
  version migration for existing repositories; changing source does not pretend
  to rewrite clones automatically.
- The v5-to-v6 migration moves the complete project-owned index payload from
  `CLAUDE.md` to root `AGENTS.md`, preserving root-relative links, replaces
  `CLAUDE.md` with the managed template, removes the obsolete sidecar, swaps the
  two configured paths, and writes `harness_version = 6` last. It stops rather
  than guessing when an unrelated non-empty `AGENTS.md` already exists.

This repository is the explicit collision case: its tracked `AGENTS.md`
already contains operator-authored rules and its v5 `CLAUDE.md` contains the
project index. The current task authorizes one deliberate reconciliation that
preserves both sets in `AGENTS.md`; that decision is not generalized into an
automatic merge for other repositories.

The official runtime contracts support this split: Codex and OpenCode use
committed `AGENTS.md` project guidance, while Claude Code documents importing an
existing `AGENTS.md` from `CLAUDE.md` to avoid duplicated instructions.

## Acceptance

- Fresh bootstrap creates the exact managed `CLAUDE.md` and a distinct
  project-owned `AGENTS.md`; project knowledge never enters the template.
- A disposable v5 repository migrates with its configured index payload retained
  in `AGENTS.md`, root-relative links intact, and the obsolete sidecar removed.
- The gate rejects template drift, project indexes above 200 lines, missing
  inline scopes, and any remaining external index-scope declaration.
- Installed Claude Code, Codex, and OpenCode load the project instructions by
  their documented path, or the unavailable runtime is recorded without a
  portability claim.
- Unit tests, repository gate, installer/mirror checks, and real `doc-create` /
  `doc-start` flows pass. Unit tests alone are not release proof.
