# Documentation Harness Contract

This document defines what the harness guarantees. Command prose and checker
behavior must agree with it.

## Environments

The same documentation model serves Claude Code, Codex, and OpenCode. Tool
integration may differ: Codex discovers user-level skills under
`$HOME/.agents/skills`; deprecated custom prompts under `~/.codex/prompts`
are not part of the design. OpenCode-only orchestration remains outside this
cross-tool contract.

## Layers and ownership

- The configured index file is thin and owns repository inventory, roles, and
  ownership.
- `docs/README.md` routes readers without duplicating the index.
- Durable documents describe verified, long-lived facts.
- `docs/active-context.md` is a volatile snapshot of current state, unresolved
  work, and immediate next steps. It is reconsolidated, not appended to.
- Execution plans describe bounded multi-step work and expose state in YAML
  frontmatter.

## Mechanical and semantic guarantees

The deterministic, repository-local mechanical gate recursively indexes
Markdown under `docs/`, plus the root README and configured index. It checks:

- relative Markdown links;
- `.doc-profile` keys and values;
- execution-plan status metadata;
- the configured index and meta-repository inventory ownership;
- baseline format and ancestry when a baseline is present.

A clean mechanical gate means the document graph and metadata are internally
consistent. It does **not** mean prose matches runtime behavior.

The semantic critic reviews factual claims in changed documentation against
code and wiring. It classifies unsupported claims instead of guessing and
enforces English for repository artifacts. Session consolidation requires a
clean mechanical gate and zero stale semantic claims; unverifiable claims stay
explicit in the result.

## Profile schema

`docs/.doc-profile` uses `key = value` records:

- `harness_version`: required protocol version shared by the repo docs, the
  installed commands, and the mechanical checker;
- `schema_version`: `1` in every newly created profile; a missing value is
  accepted only for backward compatibility with legacy profiles;
- `mode`: `leaf` or `meta`;
- `index_file`: repository-relative existing Markdown index;
- `inventory_ignore`: optional comma-separated top-level directory names for
  meta-repository inventory checks;
- `build`: optional smoke/build command used before code changes; omit the key
  when no command is known;
- `smoke`: optional smoke command when it is distinct from `build`;
- `index_max_lines`: optional non-negative thin-index limit; `0` disables
  that size check.

Unknown keys and invalid enum values are errors. Comments are explanatory only;
a commented `build` example is not a configured build command. Defaults keep
non-versioned checker use possible, but every command requires an exact harness
version match before doing any work.

## Harness compatibility handshake

Every `doc-*` workflow embeds the protocol version it implements and compares
it with `harness_version` before reading context, running consolidation, or
changing repository documentation.

- Equal versions proceed normally.
- A missing or lower repository version means the installed commands are newer.
  The workflow stops and offers an explicit `docs/` migration through
  `doc-create`; it never migrates implicitly.
- A higher repository version means the installed commands are stale. The
  workflow stops and directs the user to upgrade and reinstall mrcall-ai-kit.
- Downgrading repository docs is never offered.

An authorized docs migration changes only harness-owned metadata and structure,
preserves repository knowledge, writes the new version last, and must finish
with a clean mechanical gate. Codex entry-point skills inherit the version from
their installed shared `WORKFLOW.md`, so all three environments use the same
handshake.

## Execution-plan schema

Every Markdown file under `docs/execution-plans/` except placeholders has YAML
frontmatter with one `status` value:

- `planned`: accepted but not started;
- `active`: currently being executed;
- `blocked`: unable to advance until its recorded condition changes;
- `completed`: all required work and verification are done;
- `superseded`: replaced or deliberately abandoned, with the reason recorded.

Commands derive plan state from metadata, never from prose. Only `completed`
plans are finished; the other states remain visible with their labels.

## Baseline semantics

`doc_baseline_commit` identifies the code commit whose behavior has been
reconciled into living documentation. It must resolve and be an ancestor of
`HEAD`.

The documentation update recording that baseline can be committed after the
referenced code commit. A docs-only reconciliation commit after the baseline is
therefore not product drift. Start-of-session reporting distinguishes
code-bearing commits from docs-only commits when possible and reports
uncommitted changes separately.

The end workflow reviews committed changes since the baseline and relevant
working-tree changes. It advances the baseline only after the mechanical gate
passes and semantic review has zero stale claims.
Advancing it to `HEAD` records what was reviewed; it cannot represent an
uncommitted code change as part of that commit.

## Living-context discipline

`active-context.md` contains only current facts:

- verified capabilities that materially affect current work;
- work in progress or awaiting verification;
- unresolved failures and blockers;
- immediate next actions.

It does not retain per-session done lists, corrected theories, or chronological
notes. A durable architectural fact belongs in a durable doc; a decision fully
captured by a completed plan or brief needs no duplicate here. Session
narrative that is neither of those — the detailed "what we tried, what broke,
what we verified" record of a session — moves to `docs/active-context-archive.md`
instead of being deleted outright: dated sections, newest first, preserved
verbatim. Nothing that was ever true is lost, it is just no longer on the path
every session pays to read. Contradictory current and historical claims are a
semantic failure even when the mechanical gate is clean.

The archive is deliberately outside `doc-start`'s Phase 2 (volatile-layer) read
set — it exists to answer "when did we do X", read on demand, not to be loaded
every session start. It is still an ordinary file under `docs/`: the mechanical
gate indexes it like any other Markdown file (dead links inside it are still
checked; nothing in `doc-check.py` treats it specially or exempts it from
`index_docs()`), and it is discoverable through a routing line in
`docs/README.md`, the same as every other durable doc.

Two independent points enforce this, so a lazy "consolidate" (prepend today's
notes, touch nothing else) cannot silently drift the file into a changelog for
months unnoticed: `doc-end` Phase 3 archives-then-trims as part of normal
per-session reconsolidation (proactive), and the `doc-critic` skill
independently checks the file's shape — extra dated headings, narrative
prose, well over the line target — and repairs it directly, archive and
rewrite, whenever it finds a violation (reactive safety net, catches it even
when Phase 3 was done sloppily).
