# mrcall-ai-kit

Docs that keep up with AI-speed coding. A small harness for **Claude Code**,
**Codex**, and **OpenCode** that brackets every work session with three
commands, so each of your repos keeps a set of docs that stays small, current,
and verified against the code — instead of rotting into a changelog nobody
trusts. Plus, for OpenCode only, multi-model orchestration tooling.

## Why you'd want it

- **Sessions start oriented.** `doc-start` loads the smallest useful context
  and tells you immediately whether the docs have drifted from the code.
- **Sessions end consolidated.** `doc-end` writes back what actually happened,
  then a deterministic checker and an independent critic verify the docs
  against the code before anything gets to call itself done.
- **Nothing rots silently.** Dead links, stale plans, a doc describing a
  feature that no longer exists — caught by a gate, not by hope.
- **You always know where work stands.** Anything substantial leaves a dated
  trace, so "is this finished, in progress, or just an idea?" still has an
  answer months later.

## Install (2 minutes)

```bash
git clone https://github.com/malemi/mrcall-ai-kit.git
cd mrcall-ai-kit
./install.sh
```

That's the whole install. The script detects which tools you already have,
asks what you want, prints the exact list of files it is about to write, and
writes nothing until you say yes. It installs **globally** (your `~/.claude`,
`~/.agents`, `~/.config/opencode`, `~/.config/mrcall-ai-kit`) — never inside
your repos. Requirements: `bash`, `git`, `python3`.

Then:

1. Restart your Claude Code / Codex / OpenCode sessions so they pick up the
   new commands.
2. In each repo you want covered, run `doc-create` once (`/doc-create` as a
   slash command; `$doc-create` in Codex) to bootstrap its `docs/`.

From there the routine is two commands: `doc-start` when you sit down,
`doc-end` when you stop.

### Non-interactive / CI

Every prompt has a flag, `--dry-run` prints the plan and installs nothing, and
with no TTY the script exits instead of hanging. Everything at once:

```bash
./install.sh --environment all --features all \
             --mode symlink --on-exist backup --yes
```

`./install.sh --help` lists every flag and exactly what each feature installs.

## Uninstall

```bash
./uninstall.sh
```

Reads the installer's own log and removes every file it put there — symlinks
and copies alike.

## What's inside

- **The doc-harness** (Claude Code + Codex + OpenCode): the `doc-create` /
  `doc-start` / `doc-end` workflows, a mechanical gate (`doc-check.py`), and a
  semantic critic that checks changed docs against the implementation.
- **OpenCode extras**: an interactive `/orchestrator` that plans with you,
  delegates to a roster of 16 worker models, and verifies results — with a
  watchdog that kills hung or over-budget workers — plus `/migrate-check` for
  moving your setup over from Claude Code.
- **Claude Code opt-in model router** (`--features router`): run the session
  on a cheap model that answers trivial prompts itself and delegates
  everything else to pinned-model workers (`worker-sonnet` / `worker-opus` /
  `worker-fable`). Off by default — a `UserPromptSubmit` hook stays dormant
  until `/router on` flips a flag file; `/router off` undoes it. Delegated
  workers share continuity across turns via a per-session memory file that
  `/doc-end` folds into `active-context.md` when the session wraps up.
- **`/ai-help`**: lists everything actually installed — commands, skills,
  agents, with their descriptions — by reading the filesystem, not a written
  list that goes stale.

Want the full rules the harness enforces? They live in
[`docs/documentation-harness.md`](docs/documentation-harness.md).

## License

MIT — use it, fork it, improve it.
