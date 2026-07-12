# Regole operative globali per OpenCode

Queste regole prima venivano iniettate via hook a ogni prompt in Claude Code.
In OpenCode vivono qui come istruzioni globali.

Le modifiche all'installazione OpenCode (plugin patchati, hack, workaround)
sono documentate in [`HACKS.md`](./HACKS.md).

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
