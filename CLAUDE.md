# mrcall-ai-kit — index

**Stack**: Bash + Python + Markdown
**Entry point**: `install.sh` (global installer)
**Do not break**: All docs in English; this index is the single source of truth and carries no duplicated inventory — other docs point here

<!-- orientation ends -->

<!-- doc-scope:start -->
Scope: Canonical thin index for repository ownership, layout, and documentation routing; detailed contracts live in linked docs.
<!-- doc-scope:end -->

Thin index for AI tools. Pointers only; no prose, no duplicated inventory.

Reusable AI-tool config for **Claude Code**, **Codex**, and **OpenCode**: a
documentation harness plus (OpenCode-only) multi-model orchestration and
migration tooling, and (Claude Code-only) an opt-in model router.
User-facing overview lives in [`README.md`](README.md).

## Docs

- [`docs/README.md`](docs/README.md) — index of transversal docs.
- [`docs/active-context.md`](docs/active-context.md) — volatile state
  (last done / in progress / next).
- [`docs/execution-plans/`](docs/execution-plans/) — active plans.
- [`docs/scope-guard.md`](docs/scope-guard.md) — scope declaration and optional
  runtime guard contract.

## Layout

- `shared/` — source workflows, `doc-check.py` gate, and `doc-critic` skill.
- `claude/` — Claude Code-only: pinned-model worker agents the doc workflows
  delegate to, plus the opt-in model router (`commands/router.md`,
  `scripts/router-hook.py`).
- `codex/` — Codex-native skill entry points for the shared doc workflows.
- `opencode/` — OpenCode-only: orchestration, worker agents, watchdog,
  migration tooling.
- `install.sh` / `uninstall.sh` — global installer / uninstaller.

## Conventions

- **Nothing enters unless it reduces uncertainty** — a sentence, an
  abstraction, a flag. If its absence would change nothing the reader believes
  or does, delete it. Logs are exempt and take everything. See
  [`docs/principles.md`](docs/principles.md).
- All docs in English.
- Single source of truth = this index; other docs point here.
- Work traces: orchestrated or multi-session work starts by creating
  `docs/briefs/YYYY-MM-DD-<slug>.md` (what/why) +
  `docs/execution-plans/YYYY-MM-DD-<slug>.md` (status frontmatter) before
  execution.
