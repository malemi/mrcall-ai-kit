# MrCall AI-Kit

Keep up with AI-speed coding.

Use **Claude Code**, **Codex**, and **OpenCode**, collaborate with other
developers: AI-Kit memorizes intra and inter-sessions, allows you to setup
orchestrators, and it comes with specialized agents.

Powerful. Easy to install, easier to use.

## Why you should use it

- Claude wants to go on credits? Shift to OpenCode or Codex
- Setup a simple LLM router which decides which model should be used for each query
- Different agents can work together on a shared memory
- You never start from stale documentation
- You never end a session with documentation half-updated
- Each routing document can declare its exact purpose and boundary in a
  mechanically checked scope block

## Install

```bash
git clone https://github.com/malemi/mrcall-ai-kit.git
cd mrcall-ai-kit
./install.sh
```

That's the whole install. The script detects which tools you already have,
asks what you want. It installs **globally** (your `~/.claude`,
`~/.agents`, `~/.config/opencode`, `~/.config/mrcall-ai-kit`) — never inside
your repos.

Then:

1. Restart your Claude Code / Codex / OpenCode sessions so they pick up the
   new commands.
2. In each repo you want covered, run `doc-create` once (`/doc-create` as a
   slash command; `$doc-create` in Codex) to bootstrap its `docs/`.

From there the routine is two commands: `doc-start` when you sit down,
`doc-end` when you stop.

## Uninstall

```bash
./uninstall.sh
```

Reads the installer's own log and removes every file it put there — symlinks
and copies alike.

## Commands

- **`doc-create`** — set up a project's notes, once.
- **`doc-start`** — run this to begin a work session.
- **`doc-end`** — run this to close one; the notes get corrected to match
  reality.
- **`/router`** (Claude Code) — keeps small work local and routes substantial
  work to a fitting specialist when delegation is worthwhile.
- **`/ai-help`** (Claude Code) — the current, accurate list of everything
  installed.
- **`/orchestrator`** (OpenCode) — autonomous engineering lead that implements
  directly or delegates bounded work when coordination pays off.
- **`/migrate-check`** (OpenCode) — checks a move over from Claude Code.

There's also a **memory** — a short, current account of a project, and of
each session, that keeps itself up to date — and **agents**: AI helpers
pinned to specific models, brought in automatically for particular jobs.

Want the full detail? See
[`docs/documentation-harness.md`](docs/documentation-harness.md).
The optional runtime enforcement design and its current verification status are
in [`docs/scope-guard.md`](docs/scope-guard.md).

## License

MIT — use it, fork it, improve it.
