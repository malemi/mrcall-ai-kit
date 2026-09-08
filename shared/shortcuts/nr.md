---
description: Answer one question now — no tools, no subagents, no work trace, no review gates. Suspends the harness machinery for a single turn, never the gates that govern doing work. Run ONLY when the operator asks for it by name; never self-trigger on a plain question or infer it from context.
---

Answer the question below from what you already know, in this turn, and stop.

Question: $ARGUMENTS

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
fact. This command removes the checking, so a confident unverified answer is the
exact failure it makes possible.

If the argument asks for an action or a change rather than a question, decline in
one line and say that the normal path applies. This command suspends
investigation, never the gates that govern doing work.

If no question follows at all, say so in one line and stop. Do not adopt the
previous turn as the question — this command suspends the checking, so guessing
what was meant is the one thing it must not do.
