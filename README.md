# mrcall-ai-kit

Reusable AI-tool config for **Claude Code** and **OpenCode**: a documentation
harness that keeps docs from rotting, plus (OpenCode-only) multi-model
orchestration and migration tooling.

## Install

```bash
git clone https://github.com/malemi/mrcall-ai-kit.git
cd mrcall-ai-kit
./install.sh
```

That's the whole install. The script detects which tools you already have, asks
what you want, prints the exact list of files it is about to write, and writes
nothing until you say yes. Requirements: `bash`, `git`, and `python3` (used by
the doc-harness gate).

Then:

1. Restart your Claude Code / OpenCode sessions so they pick up the new
   commands, skills and agents.
2. Inside any repo you work on, run `/doc-create` to bootstrap its `docs/`.

The install is **global** — commands land in `~/.claude/` and/or
`~/.config/opencode/`, and `doc-check.py` in `~/.config/mrcall-ai-kit/`. Nothing
is written inside your repos; per-repo `docs/` is created later by `/doc-create`.

### Non-interactive install

Every question has a flag; passing it skips that prompt. Everything at once:

```bash
./install.sh --environment both --features all \
             --mode symlink --on-exist backup --yes
```

Just the doc-harness for Claude Code:

```bash
./install.sh --environment claude --features doc-harness \
             --mode symlink --on-exist skip --yes
```

| Flag | Values | Meaning |
|------|--------|---------|
| `--environment` | `claude`, `opencode`, `both` | which tool(s) to install into |
| `--features` | `doc-harness`, `orchestration`, `workers`, `migrate` (comma list, or `all`) | what to install |
| `--mode` | `symlink`, `copy` | `symlink` = edit the kit = edit your config, and the clone must stay where it is; `copy` = frozen snapshot, clone disposable |
| `--on-exist` | `skip`, `overwrite`, `backup` | what to do when a target file is already there |
| `--yes` | — | skip the final confirmation |
| `--dry-run` | — | print the plan, write nothing |

`./install.sh --help` lists exactly which commands, skills and agents each
feature installs. With no TTY (CI, piped input) the script exits rather than
hang: pass the flags.

## Uninstall

```bash
./uninstall.sh
```

Removes everything the installer recorded — symlinks and copied files alike —
by reading its own install log. Nothing installed by this kit is left behind.

## What's in the kit

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

### The doc-harness (cross-tool)

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

### OpenCode-only

- **orchestration** — `/orchestrator` + the `build`/`plan`/`reviewer` agents.
- **worker agents** — 15 models (DeepSeek, Gemini, GLM, GPT, Kimi, Llama, MiMo,
  Mistral, Nemotron, Qwen, Sonnet) for multi-model delegation.
- **watchdog** — daemon that monitors workers via SSE + SQLite, kills hung ones
  on timeout or budget excess. Automatic circuit breaker for cost control.
- **migrate-from-cc** — `/migrate-check` + the migration skill.

## License

MIT — use it, fork it, improve it.
