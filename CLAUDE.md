# mrcall-ai-kit — index

Thin index for AI tools. Pointers only; no prose, no duplicated inventory.

Reusable AI-tool config for **Claude Code** and **OpenCode**: a documentation
harness plus (OpenCode-only) multi-model orchestration and migration tooling.
User-facing overview lives in [`README.md`](README.md).

## Docs

- [`docs/README.md`](docs/README.md) — index of transversal docs.
- [`docs/active-context.md`](docs/active-context.md) — volatile state
  (last done / in progress / next).
- [`docs/execution-plans/`](docs/execution-plans/) — active plans.

## Layout

- `shared/` — cross-tool (Claude Code + OpenCode): doc-harness commands,
  `doc-check.py` gate, `doc-critic` skill.
- `opencode/` — OpenCode-only: orchestration, worker agents, watchdog,
  migration tooling.
- `install.sh` / `uninstall.sh` — global installer / uninstaller.

## Conventions

- All docs in English.
- Single source of truth = this index; other docs point here.
