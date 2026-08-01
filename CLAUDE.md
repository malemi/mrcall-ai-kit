# mrcall-ai-kit — index

Thin index for AI tools. Pointers only; no prose, no duplicated inventory.

Reusable AI-tool config for **Claude Code**, **Codex**, and **OpenCode**: a
documentation harness plus (OpenCode-only) multi-model orchestration and
migration tooling.
User-facing overview lives in [`README.md`](README.md).

## Docs

- [`docs/README.md`](docs/README.md) — index of transversal docs.
- [`docs/active-context.md`](docs/active-context.md) — volatile state
  (last done / in progress / next).
- [`docs/execution-plans/`](docs/execution-plans/) — active plans.

## Layout

- `shared/` — source workflows, `doc-check.py` gate, and `doc-critic` skill.
- `codex/` — Codex-native skill entry points for the shared doc workflows.
- `opencode/` — OpenCode-only: orchestration, worker agents, watchdog,
  migration tooling.
- `install.sh` / `uninstall.sh` — global installer / uninstaller.

## Conventions

- All docs in English.
- Single source of truth = this index; other docs point here.
