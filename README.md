# mrcall-ai-kit

Docs that keep up with AI-speed coding.

**Claude Code**, **Codex**, and **OpenCode** are AI assistants that write and
edit code for you from a terminal. This kit keeps each project's notes —
what the code does, what's being worked on, what's still open — accurate
automatically, instead of rotting the way documentation always does the
moment nobody is explicitly paid to maintain it.

## Why you'd want it

- **You never start from stale notes.** Whatever the project's
  documentation says, it's guaranteed to still be true — or you're told
  immediately that it isn't.
- **You never end a session with the notes half-updated.** They always
  match what actually happened. Nobody has to remember to go fix them.
- **Nothing rots silently.** A dead link, a plan nobody finished, a feature
  that got deleted but is still described somewhere — all of it gets caught
  and fixed, instead of sitting there for months.
- **You can always tell what's going on.** Any real piece of work stays
  traceable — finished, in progress, or abandoned — never a mystery six
  months later.

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
- **`/router`** (Claude Code) — on/off switch for quick, cheap answers to
  easy questions.
- **`/ai-help`** (Claude Code) — the current, accurate list of everything
  installed.
- **`/orchestrator`** (OpenCode) — hands a big task to several AI models at
  once.
- **`/migrate-check`** (OpenCode) — checks a move over from Claude Code.

There's also a **memory** — a short, current account of a project, and of
each session, that keeps itself up to date — and **agents**: AI helpers
pinned to specific models, brought in automatically for particular jobs.

Want the full detail? See
[`docs/documentation-harness.md`](docs/documentation-harness.md).

## License

MIT — use it, fork it, improve it.
