---
name: nr
description: Answer one question right now, with no tools, no subagents, no work trace, and no review gates for that turn — suspends the harness machinery for a single turn, never the gates that govern doing work. Invoke ONLY when the operator explicitly asks for this skill by name (e.g. says "nr"); never self-trigger on a plain question or infer this from context.
---

# nr — answer now, machinery suspended for this turn

Answer the question below from what you already know, in this turn, and stop.
The question is whatever the operator said when invoking this skill — there is
no separate argument slot; take it from their own message, not from a tool.

For this turn only:

- Use no tool. Read nothing, run nothing, search nothing.
- Delegate to no subagent.
- Write no brief, no execution plan and no session-memory update, and open no
  review gate.
- Answer in a few sentences. No preamble, no restating of the question, no
  offer of further work.

Two limits are not suspended.

If you do not already know the answer, say so in one line and name what would
have to be checked. Never guess, and never present a plausible reconstruction as
fact. This skill removes the checking, so a confident unverified answer is the
exact failure it makes possible.

If the operator's message asks for an action or a change rather than a
question, decline in one line and say that the normal path applies. This skill
suspends investigation, never the gates that govern doing work.

If their message carries no question at all, say so in one line and stop. Do not
adopt the previous turn as the question — this skill suspends the checking, so
guessing what was meant is the one thing it must not do.
