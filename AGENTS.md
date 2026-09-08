# Project operating rules

<!-- doc-scope:start -->
Scope: Project-owned operating rules and thin repository index; harness protocol
lives in managed `CLAUDE.md`, and durable detail lives under `docs/`.
<!-- doc-scope:end -->

## Fixing bugs

Never claim something works until you have run it the way the final user
runs it (REPL, CLI, API, browser). Unit tests don't count. Do not think
you have fixed a bug UNLESS it has been tested in the real environment.
Do not assume something is working unless it has been Q&A'd (yours and the user's)
tests. Do not commit bug fixes unless you are sure they actually work,
because tested in real-life scenarios.

## Fix the root cause — never a workaround that defers it

If something is broken — a tool, a search, a query, a code path — FIX
THE ROOT CAUSE. Do not paper over it with a one-off workaround (a manual
crawl, a hand-assembled result, a "just this once" hack) and then end
the session, leaving the same broken thing to resurface next time. A
workaround that defers the bug is not a fix. When you hit a broken or
missing capability: understand WHY it fails, correct it in the
code/tool, re-run it, and only then continue the task. The session must
end with the underlying problem fixed, not re-deferred.

## Planning — no shortcuts

The following shortcuts are FORBIDDEN — they are not "optimizations",
they are bugs:

1. Reading only the first N chars/lines of a document. If the doc is
   20k chars, read all 20k. Do not pass `limit` to Read, do not pipe
   to `head`, do not truncate.
2. Capping search/list results (limit=5, head -5, top_k=10). Fetch
   them all. If the result set is genuinely huge, ask first.
3. Using regex/grep/string-matching to parse unstructured text
   (prose, HTML, LLM output, news articles). Call an LLM instead.
   Regex is for structured input only.
4. Picking a cheaper/smaller model to "save cost". Use the model the
   task needs. If unsure, use Opus.

Correctness beats efficiency. Always. Delegate to subagents to spare
context, never to spare cost.

## Operating

Do not ask questions to the user unless you really cannot answer (e.g.
"Can you pls run this query" if the DB is accessible to you, obvious
security decisions). In general, you must plan -> develop -> test [as
close to real life] -> plan ... Unit tests are syntactic tests, we need
semantic tests.

## Repository index

**Stack**: Bash + Python + Markdown
**Entry point**: `install.sh` (global installer)
**Do not break**: All docs in English; this index is the single source of truth
and carries no duplicated inventory — other docs point here

<!-- orientation ends -->

Thin index for AI tools. Pointers only; no duplicated durable prose.

Reusable AI-tool config for **Claude Code**, **Codex**, and **OpenCode**: a
documentation harness plus (OpenCode-only) multi-model orchestration and
migration tooling, and (Claude Code-only) an opt-in model router. User-facing
overview lives in [`README.md`](README.md).

### Docs

- [`docs/README.md`](docs/README.md) — index of transversal docs.
- [`docs/active-context.md`](docs/active-context.md) — volatile state
  (last done / in progress / next).
- [`docs/execution-plans/`](docs/execution-plans/) — active plans.
- [`docs/scope-guard.md`](docs/scope-guard.md) — scope declaration and optional
  runtime guard contract.

### Layout

- `shared/` — source workflows, `doc-check.py` gate, `CLAUDE.md` template,
  `doc-critic` skill, and `shortcuts/` (the `nr` and `av` instruction overrides
  an operator pulls on demand).
- `claude/` — Claude Code-only: pinned-model worker agents the doc workflows
  delegate to, plus the opt-in model router (`commands/router.md`,
  `scripts/router-hook.py`).
- `codex/` — Codex-native skill entry points for the shared doc workflows and
  for the shortcuts, which Codex has no operator-typed command form for.
- `opencode/` — OpenCode-only: orchestration, worker agents, watchdog, and
  migration tooling.
- `install.sh` / `uninstall.sh` — global installer / uninstaller.

### Conventions

- **Nothing enters unless it reduces uncertainty** — a sentence, an
  abstraction, a flag. If its absence would change nothing the reader believes
  or does, delete it. Logs are exempt and take everything. See
  [`docs/principles.md`](docs/principles.md).
- All docs are in English.
- Single source of project truth = this index; other docs point here.
