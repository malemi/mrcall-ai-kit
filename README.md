# mrcall-ai-kit

Reusable AI-tool config for **Claude Code** and **OpenCode**: a documentation
harness that keeps docs from rotting, plus (OpenCode-only) multi-model
orchestration and migration tooling.

Content is routed by tool-compatibility — the installer only puts each piece
where it works:

```
shared/     cross-tool (Claude Code + OpenCode)
  commands/   doc-create, doc-start, doc-end
  scripts/    doc-check.py       → installed once to ~/.config/mrcall-ai-kit/
  skills/     doc-critic
opencode/   OpenCode-only
  commands/   orchestrator, migrate-check
  agents/     build, plan, reviewer, + 15 worker models
  skills/     orchestrator, migrate-from-cc
              watchdog.py, watchdog-cli, watchdog_client.py
```

## The doc-harness (cross-tool)

A single source of truth (one thin index file, `CLAUDE.md`) + a gate that makes
"documented" mean "true". Three commands:

- **`/doc-create`** — bootstrap a repo's `docs/` skeleton, its `.doc-profile`,
  and a thin index. Idempotent; never fabricates knowledge.
- **`/doc-start`** — load the smallest high-signal context and run the gate, so
  drift is visible at the start of every session.
- **`/doc-end`** — reconsolidate the docs to reality, then verify against code
  (mechanical `doc-check` + the semantic `doc-critic` skill) before advancing
  the baseline.

`doc-check.py` (mechanical gate) fails on dead doc links and, in meta-repos, on
repo-inventory drift or a duplicated repo-index. `doc-critic` is the semantic
pass: it flags any doc that describes a feature/endpoint/file that doesn't exist
or isn't wired (dead code documented as live).

Git hooks are intentionally NOT shipped — a pre-commit hook is repo-local
plumbing you add yourself (`.githooks/pre-commit` running the gate + `git config
core.hooksPath .githooks`). Enforcement here flows through the commands.

## OpenCode-only

- **orchestration** — `/orchestrator` + the `build`/`plan`/`reviewer` agents.
- **worker agents** — 15 models (DeepSeek, Gemini, GLM, GPT, Kimi, Llama, MiMo,
  Mistral, Nemotron, Qwen, Sonnet) for multi-model delegation.
- **watchdog** — daemon that monitors workers via SSE + SQLite, kills hung ones
  on timeout or budget excess. Automatic circuit breaker for cost control.
- **migrate-from-cc** — `/migrate-check` + the migration skill.

## Install

Interactive by default; pass flags for non-interactive / CI use.

```bash
git clone https://github.com/malemi/mrcall-ai-kit.git
cd mrcall-ai-kit
./install.sh
```

Flags (any provided value skips its prompt):

- `--environment claude|opencode|both`
- `--features doc-harness,orchestration,workers,migrate` (or `all`)
- `--mode symlink|copy` — symlink = edit the kit = edit your config
- `--on-exist skip|overwrite|backup`
- `--yes` — skip the final confirmation
- `--dry-run` — show the plan, write nothing

The installer detects which tools are present, offers only content valid for the
chosen tool(s), shows a plan, and asks before writing. Global install only
(commands live in `~/.claude/` and/or `~/.config/opencode/`); a repo's per-repo
`docs/` is set up separately by `/doc-create`.

After install, restart your Claude Code / OpenCode sessions, then run
`/doc-create` inside a repo to bootstrap its docs.

## Uninstall

```bash
./uninstall.sh
```

Removes everything the installer recorded — symlinks and copied files alike —
by reading its own install log. Nothing installed by this kit is left behind.

## License

MIT — use it, fork it, improve it.
