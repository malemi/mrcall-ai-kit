---
description: Bootstrap or explicitly migrate this repository's documentation harness.
allowed-tools: Bash(git *) Bash(ls *) Bash(mkdir *) Bash(cat *) Bash(cp *) Bash(cmp *) Bash(rm *) Bash(python3 *) Write Edit
---

Bootstrap this repository's documentation harness. It is idempotent: create only
missing project content, replace only harness-managed content, and never invent
architecture, conventions, commands, or ownership. Everything written is in
English.

## Harness version and template preflight — before every mutation

This command implements `harness_version = 8`. Read all of
`docs/.doc-profile`, when present, before inspecting project documentation.

- Equal to `8`: continue.
- Missing or lower than `8`: stop unless the user explicitly authorized this
  docs upgrade. Report: `Harness version mismatch: repo docs are older than the
  installed commands (docs: <version|legacy>, commands: 8). Upgrade docs/
  explicitly with doc-create, or cancel and leave the repo unchanged.`
- Greater than `8`: stop. Report: `Harness version mismatch: installed commands
  are older than the repo docs (commands: 8, docs: <version>). Upgrade
  mrcall-ai-kit and reinstall its commands; docs/ must not be downgraded.`
- No profile means a fresh bootstrap, not a version mismatch.

Resolve the canonical managed template before changing anything. Installed
commands use `~/.config/mrcall-ai-kit/CLAUDE.template.md`; a source-tree run may
use `shared/templates/CLAUDE.md`. If neither exists, stop with no repository
changes. Read the whole template, require one valid inline `doc-scope` block,
the exact `@AGENTS.md` import, and the generic work-trace rule. Never reproduce
or customize its prose: copy it byte-for-byte and verify with `cmp`.

There is no implicit migration in `doc-start` or `doc-end`.

## Explicit migrations

Run every collision and safety check before the first write. Preserve project
knowledge verbatim unless a historical harness marker makes a removal
mechanical. Write `harness_version = 8` last; never downgrade.

### From `7`

Require the configured ownership paths (`index_file = AGENTS.md`,
`harness_file = CLAUDE.md`) and the exact v7 managed `CLAUDE.md` shape: the
documentation-harness title, `@AGENTS.md`, one canonical inline scope, the
work-trace rule, and the autonomous engineering-lead contract, with no project
prose. Replace only `CLAUDE.md` byte-for-byte with the v8 template, validate all
required routing scopes, then write `harness_version = 8` last. A differing
file is a collision; stop rather than discarding content whose ownership is
unclear.

### From `6`

Require the configured ownership paths (`index_file = AGENTS.md`,
`harness_file = CLAUDE.md`) and the exact v6 managed `CLAUDE.md` shape: the
documentation-harness title, `@AGENTS.md`, one canonical inline scope, and the
work-trace rule, with no project prose. Replace only `CLAUDE.md` byte-for-byte
with the v8 template, validate all required routing scopes, then write
`harness_version = 8` last. A differing file is a collision; stop rather than
discarding content whose ownership is unclear.

### From `5`

Version 5 normally has `index_file = CLAUDE.md` and
`harness_file = .claude/rules/doc-harness.md`. The former is project content;
the latter is obsolete harness content.

1. Read the complete configured index and sidecar. Require the v5 paths and
   recognizable canonical sidecar markers; otherwise stop with a precise
   conflict report.
2. If root `AGENTS.md` is absent or empty, copy the complete old index payload
   there. If it is non-empty and byte-identical to the old index, keep it. If it
   contains different content, stop before changing anything: merging two
   project instruction sets needs an explicit human reconciliation, never a
   heuristic merge.
3. Add exactly one canonical inline `doc-scope` block to `AGENTS.md` if absent,
   describing its project-owned routing and instruction boundary. Do not remove
   or shorten project prose to meet the line budget; report an over-limit index.
4. Replace root `CLAUDE.md` byte-for-byte with the canonical template and remove
   `.claude/rules/doc-harness.md`. If the scope guard protects the sidecar,
   perform its explicit unmark protocol first; do not bypass the guard.
5. Set `index_file = AGENTS.md` and `harness_file = CLAUDE.md`, validate all
   required routing scopes, then write `harness_version = 8` last.

A repository whose two project instruction files were already deliberately
reconciled may proceed only after that reconciliation is explicit in the
current task; that is authorization for the known content decision, not a rule
that future migrations may guess equivalence.

### From `4` or earlier, including legacy

First preserve the configured index as the project payload. Remove only the
canonical root `doc-scope` block and exact harness-owned work-trace stanza used
by pre-v5 versions; their exact markers make this mechanical. Never choose
repository prose to move or discard. Then apply the v5 ownership migration
above. Add only missing required profile keys, preserve comments and deliberate
optional-key omissions, and surface legacy gate failures rather than inventing
content to silence them.

For every older version, also repair `docs/active-context.md` if it violates the
living-snapshot contract: only `State now`, `Unresolved`, and `Next`, with
historical narrative moved verbatim to `docs/active-context-archive.md`. Follow
the in-session repair branch of `doc-critic`, report before/after line counts,
and discard nothing.

## Step 1 — Detect current state

- Detect `docs/`, `docs/.doc-profile`, root `CLAUDE.md`, and root `AGENTS.md`.
- Detect independent Git repositories directly below the root to choose `meta`
  versus `leaf`; report what was actually found.
- On fresh bootstrap, an existing `AGENTS.md` is project content: preserve it
  and add only the required inline scope when absent. An existing `CLAUDE.md`
  that differs from the template is a collision; stop rather than treating it
  as disposable project content without explicit migration authorization.

## Step 2 — Create the profile

Create `docs/.doc-profile` when absent; show and preserve it when already
current. A fresh profile is:

```text
harness_version = 8
schema_version = 1
mode = meta | leaf
index_file = AGENTS.md
harness_file = CLAUDE.md
inventory_ignore =
index_max_lines = 200
# doc_max_lines = 400
# build = <executable smoke command>
```

The file is machine-readable `key = value` data. Required keys are
`harness_version`, `schema_version`, `mode`, `index_file`, `harness_file`,
`inventory_ignore`, and `index_max_lines`. In v6 the two paths are fixed by the
ownership contract: `AGENTS.md` is project-owned and `CLAUDE.md` is
harness-managed. `build`, `smoke`, and `doc_max_lines` are optional; omit values
that cannot be detected and never invent commands.

## Step 3 — Create only missing structure

- `CLAUDE.md`: copy the canonical template byte-for-byte.
- `AGENTS.md`: preserve an existing project file. If missing, create a thin
  project index with a short introduction, one canonical inline scope, and
  pointers to `docs/`. In a detected meta-repo add a `## Services` table using
  only repositories actually present; leaf repositories need no table.
- `docs/active-context.md`: baseline frontmatter, one inline scope, and only
  `State now`, `Unresolved`, and `Next`; it is a current snapshot, not a log.
- `docs/README.md`: thin transversal-doc router with one inline scope. Repository
  inventory and ownership live only in the project-owned `AGENTS.md`.
- `docs/execution-plans/` and `docs/briefs/`, with `.gitkeep` when a directory
  would otherwise be empty.
- Add `docs/sessions/` to `.gitignore`; do not create that runtime directory.
- Optional empty-but-titled stubs only when useful:
  `docs/known-issues-and-solutions.md`, `docs/quality-grades.md`, and
  `docs/harness-backlog.md`. Never fabricate architecture or conventions docs.

Every required routing file has exactly one canonical declaration:

```markdown
<!-- doc-scope:start -->
Scope: <concise, non-empty purpose and boundary, optionally continued>
<!-- doc-scope:end -->
```

Project prose belongs in `AGENTS.md` or durable docs, never in managed
`CLAUDE.md`. The 200-line thin-index limit applies to `AGENTS.md` only.

Every execution plan has YAML frontmatter with exactly one lifecycle value:
`status: planned | active | blocked | completed | superseded`. Orchestrated or
multi-session work starts with a matching dated brief and plan pair before
execution: `docs/briefs/YYYY-MM-DD-<slug>.md` and
`docs/execution-plans/YYYY-MM-DD-<slug>.md`.

## Step 4 — Verify and hand off

Compare repository `CLAUDE.md` to the resolved template byte-for-byte. Run:

`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo .`

For a source-tree verification, run `shared/scripts/doc-check.py` with
`MRCALL_DOC_HARNESS_TEMPLATE` pointing at the source template. Fix
harness-owned violations, dead links, and detected inventory drift; do not
rewrite project prose merely to silence an advisory. Re-run to a clean gate.

Git hooks are out of scope. If requested, describe the optional pre-commit hook
that calls the gate; do not install it implicitly.

## Output

`Doc-harness bootstrapped in <repo> (<mode> mode, harness v8). Created: [files]. Migrated: [files or none]. Profile: docs/.doc-profile. Gate: clean. Next: doc-start.`
