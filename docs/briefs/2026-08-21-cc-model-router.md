# A model router for Claude Code, and the session memory it needs

**Date**: 2026-08-21 · **Plan**: [../execution-plans/2026-08-21-cc-model-router.md](../execution-plans/2026-08-21-cc-model-router.md)

## Problem

A Claude Code session pinned to a frontier model at high effort spends minutes
on every turn, including the ones that deserve a second — a "thanks", a yes/no
question, a path lookup. The obvious fix, routing each prompt to the cheapest
model that can answer it, is exactly what one does with the raw API: a small
classifier picks the tier, and the request goes there.

Claude Code cannot do that directly. Its model is session-scoped: `--model` at
launch, `/model` mid-session, and nothing else. A `UserPromptSubmit` hook can
inject context but has no field that changes the model, and there is no
built-in per-prompt routing. So the API pattern does not port as-is.

What does port is the shape of it, one level up: **the session model becomes
the classifier, and the tiers become pinned-model subagents.** Run the session
on Haiku; let Haiku answer the trivial turns itself and delegate the rest to
`worker-sonnet` / `worker-opus` / a new `worker-fable`, each pinned to its tier
by frontmatter and reached through the native `Agent` tool.

That reshapes the problem into a second one. Subagents start with a fresh
context and cannot see the conversation, so a session whose real work happens
inside workers has no continuity: every delegation starts from nothing, and
whatever the previous worker understood dies with it. Routing without a shared
memory buys speed and pays for it in amnesia.

## Decision

Build both halves, and keep them off by default.

**The router is opt-in.** The hook is registered once in `~/.claude/settings.json`
but stays dormant: its first act is to check for `~/.config/mrcall-ai-kit/router.on`
and exit silently when it is absent. Sessions that do not want routing are
untouched, at the cost of one `test -f` per prompt. `/router on|off` flips the
flag; `/router unregister` removes the hook entirely, because `uninstall.sh` is
manifest-driven and cannot revert a JSON edit.

**The memory is a short-lived `docs/active-context.md`.** Each routed session
gets `docs/sessions/<session-id>.md`: the same kind of object as the living
context — a snapshot of goal, decisions, and open threads, never a log — with
the same anti-drift contract, in the same repo, readable with `cat`.

Two decisions make it work, and both were the user's:

- **Whoever answers the turn writes it, at their own discretion.** Not Haiku.
  Making the cheapest model the librarian would funnel every worker's insight
  through the summary of the least capable participant; instead the model that
  did the work — which is the only one that knows what was load-bearing —
  records it, and a trivial turn records nothing.
- **Promotion happens at `/doc-end`.** A session file is `open` until the
  end-of-session rite reads it, lifts what deserves to outlive the session into
  `active-context.md`, and flips it to `closed`. This is not a new ritual: it
  is what `doc-end` already does for the session as a whole, with one more
  input.

Sessions that die without `doc-end` leave `open` orphans. Liveness is not
detectable — Claude Code exposes no PID or lock, only a transcript file whose
mtime cannot distinguish a dead session from an idle one — so `/router sweep`
reports rather than decides: it lists the open files with their dates and a
*probably dead* flag past 24h, and leaves the closing to a human.

**A discoverability gap surfaced mid-session and got folded in.** Between
doc-harness, the router, and worker-fable, the kit had accumulated enough
moving parts that "what do I actually have installed" stopped being
answerable from memory. `/ai-help` closes that: a command that introspects the
current environment at runtime — walks the installed commands, skills, and
agents, reads each one's frontmatter `description` — rather than a written
list that drifts the moment a new piece ships. It rides the same free-install
path as the rest of `shared/commands/`.
