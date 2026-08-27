# Scope guard: delivering a document's purpose at the instant it is written

**Date**: 2026-08-26 · **Plan**: none yet. The convention pairs a brief with an
execution plan, but the build has no go; this file records the design and the
open questions, and the plan gets written when the build is approved.

## Problem

The rules of this setup live in `CLAUDE.md`, in the model's memory files, and in
the headers of the documents themselves. All of them are prompt. An agent reads
them at session start, works for hours, and by the time it writes it is acting on
whatever survived in context. What survives is ordered by the agent's own
relevance — the thing it just built — not by the purpose of the file it is about
to open.

The concrete failure, 2026-08-26. `hb/docs/active-context.md` states in its
opening lines that it tracks only what spans repositories, and that per-repo
detail belongs in that repository's own `active-context.md`. A session had read
that. Hours later it was repairing the file for an unrelated reason and, while
its hand was already inside, added two entries about `/cs-review` and
`cs escalated` — facts about a single clone. It did not weigh the boundary and
decide wrongly. It did not weigh it at all, because that line was not in front of
it at the instant of the write.

A hook cannot judge whether a line falls inside a purpose. It can guarantee that
the purpose is on screen at the instant the line is written. The distinction is
between "I considered it and got it wrong" and "it never came up" — and only the
second one repeats forever.

## What was rejected, and why it deserves recording

The first proposal was a location gate: deny writes to `hb/docs/**` from a
session that did not start in `hb`. It is wrong twice over. It punishes exactly
the thing the operator had asked for — the cross-repo write was authorised, and
finding a problem in one repository that must be recorded in another is normal,
not an anomaly. And it does not catch the real defect: the same out-of-scope
lines written into `mrcall-cs/docs/` would have sailed through. The fault was
never *where* the write landed. It was *what* the write contained.

## The mechanism

A `PreToolUse` hook on `Write` and `Edit`. It receives the target path and does
three things.

**One — it finds out whether the file declares a purpose.** Not by heuristic. The
document declares it, and if the declaration is absent the hook returns
immediately and does nothing. No noise on ordinary files.

**Two — it puts the purpose back in front of the agent.** The scope text is
returned as context attached to the call. This is delivery, not obstruction: the
write is not blocked, but it can no longer happen without its own boundary being
in context at that moment.

**Three — it forces a stated reason for opening the file.** The first write to a
scoped file in a given session is refused, and the refusal text carries the scope
plus a demand for the reason. Being made to formulate "I am repairing the Next
list because it was routing sessions to the wrong repository" is what makes it
visible, to the agent itself, that two entries about `/cs-review` have nothing to
do with that reason. The hand is already inside the file and the marginal edit
feels free; a declared reason is what removes the *free*.

### The hook API supports all three

Verified against `code.claude.com/docs/en/hooks.md` on 2026-08-26, because point
three is the part the design lives or dies on:

- `PreToolUse` can return `additionalContext`, injected into the model's context
  **without** blocking the call. That is part two.
- It can return `permissionDecision: "deny"`, and `permissionDecisionReason` is
  fed back **to the model**, which can then react and retry. That is part three.
- `permissionDecision: "ask"` escalates to a human permission prompt. **Do not
  use it here** — it would interrupt the operator on every matching write.
- The payload carries `tool_input.file_path`, plus `session_id`, `cwd`, and
  `transcript_path`.
- Hooks fire for tool calls made by **subagents**, not only the main session. So
  delegating is not a way around the guard, and the guard does not need to be
  re-implemented per agent type.

The refusal is stateful per session and per file — the hook keeps a small record
keyed on `session_id` plus `file_path`, so the cost is one round trip per scoped
file per session, not one per write.

## Three things to get right

### The scope has exactly one source

`hb/docs/active-context.md` already states its boundary in prose, in its opening
lines. Adding a `scope:` frontmatter field would make two copies of one rule, and
two copies diverge — that is how this design kills itself within a few months.
Either the frontmatter becomes the only home and the prose header is deleted, or
the hook reads the prose header and no frontmatter field exists. One source, and
the gate can check that it is present on the files that route.

### A stale scope is worse than no scope

The field gets written once, the document's real role drifts, and the hook starts
delivering — with authority, at the exact moment of decision — a rule that no
longer describes the file. The hook cannot detect this by construction. The
`doc-critic` skill already verifies documents against reality, and comparing a
declared scope against what the file actually contains belongs there, in the same
pass that catches documented-but-nonexistent features.

### The stated reason must reach the operator

If the reason is only reasoned about, the sole reader is the agent, and the check
is back to depending on the agent's memory — which is the thing the design set out
to stop relying on. The refusal text must require the reason in the agent's
**visible** reply. The operator then sees "opening `active-context` to repair the
Next list" *before* the diff arrives, and the two unrelated entries stand out to
the operator in the same instant they stand out to the agent.

## What it does not do

It does not judge semantic relevance, and it cannot. An agent that writes
something out of scope *with the scope in front of it* still gets through. What
the design buys is a reduction of the failure class from "it never came up" to "it
came up and I got it wrong" — a much smaller class, and a correctable one, because
at that point there is a stated reason to argue with instead of a blank.

It costs one round trip per marked file per session. If the marker spreads to too
many files it becomes friction and people start working around it. It belongs
only on documents that **route** — the `active-context.md` files, the indexes, the
`CLAUDE.md` files — where one surplus line is not redundancy but noise competing
with the lines that carry the routing.

## Why it belongs in mrcall-ai-kit

The kit already ships hooks (`claude/scripts/router-hook.py`) and the `/doc-*`
harness that defines these documents in the first place. A declared scope is a
natural extension of the contract the harness already imposes: `doc-check.py` can
verify its presence on the files that route, and `doc-create` can stamp it into
the skeleton. Born here it holds for every repository that installs the kit,
instead of being a convention each project reinvents and then forgets.

## What this is, and what it is not

There is a tempting precedent: the cron operator's send authority lives in an
environment variable and never in the prompt, because the prompt is shaped by
inbound mail and a crafted message could otherwise grant itself permissions. The
analogy is worth stating precisely, because stated loosely it claims more than
this design delivers. That mechanism is a **control**: it removes the decision
from the prompt entirely, so no amount of persuasion in the prompt can reach it.
This one is a **mitigation**: it puts something back *into* the prompt, and a
prompt can always be under-read.

So the guarantee is narrower than "the agent will stay in scope", and the brief
should not pretend otherwise. The guarantee is that the boundary was present, the
reason was stated, and both are on the record — which turns a silent omission
into a decision with a witness. The test of whether it worked is not that
out-of-scope writes stop. It is that the ones which still happen come with a
stated reason the operator can argue with.
