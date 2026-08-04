# mrcall-ai-kit

Reusable AI-tool config for **Claude Code**, **Codex**, and **OpenCode**: a
documentation harness that keeps docs from rotting, plus (OpenCode-only)
multi-model orchestration and migration tooling.

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

1. Restart your Claude Code / Codex / OpenCode sessions so they pick up the new
   commands, skills, and agents.
2. Inside any repo you work on, invoke the `doc-create` workflow to bootstrap
   its `docs/` (`/doc-create` where commands are supported; `$doc-create` in Codex).

The install is **global**. Claude Code and OpenCode receive commands in their
native locations. Codex receives user-level skills under
`$HOME/.agents/skills`; its legacy `~/.codex/prompts` mechanism is deprecated
and is not the integration target. `doc-check.py` is installed once in
`~/.config/mrcall-ai-kit/`. Nothing is written inside your repos; per-repo
`docs/` is created later by the harness bootstrap workflow.

### Non-interactive install

Every question has a flag; passing it skips that prompt. Everything at once:

```bash
./install.sh --environment all --features all \
             --mode symlink --on-exist backup --yes
```

Just the doc-harness for Claude Code:

```bash
./install.sh --environment claude --features doc-harness \
             --mode symlink --on-exist skip --yes
```

| Flag | Values | Meaning |
|------|--------|---------|
| `--environment` | `claude`, `codex`, `opencode`, `all`, `both` | which tool(s) to install into; `all` selects all three, while legacy `both` means Claude Code + OpenCode |
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
shared/     cross-tool harness sources
  commands/   doc-create, doc-start, doc-end
  scripts/    doc-check.py       → installed once to ~/.config/mrcall-ai-kit/
  skills/     doc-critic
claude/     Claude Code-only
  agents/     worker-sonnet, worker-opus (pinned-model delegation targets;
              installed as part of doc-harness, not an opt-out)
codex/      Codex-native skill packages, installed atomically as directories
  skills/     doc-create, doc-start, doc-end (SKILL.md + WORKFLOW.md)
opencode/   OpenCode-only
  commands/   orchestrator, migrate-check
  agents/     build, plan, reviewer, + 16 worker models
  skills/     orchestrator, migrate-from-cc
              watchdog.py, watchdog-cli, watchdog_client.py
```

### The doc-harness (Claude Code, Codex, and OpenCode)

A single source of truth (one thin index file, `CLAUDE.md`) plus two distinct
verification layers. The harness has three workflows, exposed as slash commands where supported
and as `$doc-create`, `$doc-start`, and `$doc-end` skills in Codex:

- **`doc-create`** — bootstrap a repo's `docs/` skeleton, its `.doc-profile`,
  and a thin index. Idempotent; never fabricates knowledge.
- **`doc-start`** — load the smallest high-signal context and run the gate, so
  drift is visible at the start of every session.
- **`doc-end`** — reconsolidate the docs to reality, then verify against code
  (mechanical `doc-check` + the semantic `doc-critic` skill) before advancing
  the baseline.

`doc-check.py` is the mechanical gate. It recursively checks Markdown under
`docs/`, validates the profile and execution-plan status schema, fails on dead
relative links, and (in meta-repos) detects repo-inventory drift or a duplicated
repo index. It also reports baseline problems, including a baseline that is not
an ancestor of `HEAD`.

The mechanical gate proves structural consistency, not truth. `doc-critic` is
the separate semantic pass: it checks changed documentation against the
implementation and flags a feature, endpoint, file, or flag that does not exist
or is not wired.

`doc-end` delegates its delegable work to pinned-model workers where the
environment has them — `worker-sonnet` for mechanical execution, `worker-opus`
for independent verification (a fresh context has not been persuaded by the
reasoning that produced the docs). Two phases are never delegated: gathering
the session signal and deciding what is current, because only the session
holding the transcript can do either. A subagent that declares no model
inherits the parent's, saving context but nothing else — these workers pin
theirs, so the tier follows the task rather than whatever the session happens
to be running.

Every `doc-*` workflow first compares its embedded harness protocol version
with `harness_version` in `docs/.doc-profile`. If repo docs are older, it stops
and offers an explicit docs migration; if repo docs are newer, it stops and
requires upgrading/reinstalling the kit. No command silently migrates or
downgrades documentation.

Execution plans use machine-readable YAML frontmatter with one of these states:
`planned`, `active`, `blocked`, `completed`, or `superseded`.
`active-context.md` is a living snapshot, not a session log — pruned session
narrative moves to `active-context-archive.md` (dated, newest first, never
read at session start, queried on demand) instead of being deleted. `doc-end`
archives it proactively each session, and `doc-critic` independently checks
that it held: in-session it repairs the drift, delegated it reports it as a
finding that blocks the baseline, since deciding what is still current needs
the session transcript.
The baseline identifies the code state reconciled by the document; the
documentation edit that records it may be committed immediately after that
commit. See [`docs/documentation-harness.md`](docs/documentation-harness.md)
for the full contract.

Git hooks are intentionally NOT shipped — a pre-commit hook is repo-local
plumbing you add yourself (`.githooks/pre-commit` running the gate + `git config
core.hooksPath .githooks`). Enforcement here flows through the commands.

### OpenCode-only

- **orchestration** — `/orchestrator` + the `build`/`plan`/`reviewer` agents.
- **worker agents** — 16 models (DeepSeek, Gemini, GLM, GPT, Kimi, Llama, MiMo,
  Mistral, Nemotron, Qwen, Sonnet, Auto) for multi-model delegation.
- **watchdog** — daemon that monitors workers via SSE + SQLite, kills hung ones
  on timeout or budget excess. Automatic circuit breaker for cost control.
- **migrate-from-cc** — `/migrate-check` + the migration skill.

## License

MIT — use it, fork it, improve it.
