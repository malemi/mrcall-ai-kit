<!-- Source for /ai-tutorial. One section per CAPABILITY, not per file: the same
     command ships three times over for three runtimes, and writing its
     explanation three times is how the rest of this kit drifted.

     Each section is tagged with the installed artifact that proves the
     capability is present. `ai-tutorial.sh` prints only the sections whose
     proof it finds on disk, so a reader is never taught something they do not
     have. `tests/test_tutorial_covers_features.sh` fails when the kit ships a
     command with no section here, which is what stops this file rotting. -->

<!-- capability: doc-harness | proof: commands/doc-start.md | covers: doc-start doc-create doc-end doc-critic -->
## The documentation harness

Keeps a repository's `docs/` honest across sessions, so the next session starts
from what is true rather than from what was true in June.

`/doc-start` opens a session: it loads the smallest useful context and tells you
where the docs have drifted from the code. `/doc-end` closes one: it reconciles
the docs against what actually changed, runs a critic over them, and advances
the baseline commit. `/doc-create` bootstraps the whole structure in a repository
that has none.

Reach for it when you are about to do real work in a repository you will come
back to. The pay-off is not the writing; it is that six weeks later nobody has
to reconstruct why something is the way it is.

The mechanical half is `doc-check.py`, which the commands run for you. It checks
structure — frontmatter, statuses, sizes — never prose.

<!-- capability: ai-help | proof: commands/ai-help.md | covers: ai-help ai-tutorial -->
## `/ai-help` — what you actually have

Lists the commands, skills and agents installed for the runtime you are in right
now, read from disk rather than from a list someone maintained. `/ai-help all`
covers every runtime.

Reach for it when you cannot remember whether something is installed here or on
the other machine, or after an install, to see what landed. It also reports
whether the hook-backed features are dormant or live, which the file listing
alone cannot tell you.

<!-- capability: sc | proof: commands/sc.md | covers: sc -->
## `/sc` — a re-read pass over the answer

`/sc <your question>` answers normally, then hands the finished answer back to
the session once, against a short checklist, before you see it. The model fixes
what fails and you get the corrected version.

It exists because the rules about how to answer — run the check you just named,
say what a thing is before naming it, one idea per sentence — are already
written and get forgotten anyway, since by the end of a long turn they sit
thousands of tokens behind. The hook does not judge and calls no model: it puts
the list back in front at the one moment it can still be acted on.

Reach for it when the answer matters and is going to be long: a design question,
an explanation you will act on, anything you would otherwise have to read twice.
Not worth it for "is the service up".

`/sc on` makes every answer take the pass, `/sc off` stops it. The checklist is
`~/.config/mrcall-ai-kit/reread-checklist.md` and you can edit it. Answers under
500 characters are skipped, because the pass costs a full extra model turn.

<!-- capability: router | proof: commands/router.md | covers: router -->
## `/router` — cheap session, expensive workers

Runs the conversation itself on a cheap model that answers trivia and does
narrow work, and delegates the substantial pieces to workers pinned to stronger
models. `/router on` activates it, `/router off` stops it.

It also gives a routed session a shared memory file under `docs/sessions/`, so
work survives across delegations — a subagent starts with an empty context, and
without that file everything the previous worker understood is lost.

Reach for it on long sessions with a lot of mechanical work in them. Not for a
single hard question, where the delegation costs more than it saves.

`/router sweep` lists session files still open, with their age, so you can spot
the ones a dead session left behind. It never closes one itself.

<!-- capability: scope-guard | proof: commands/scope-guard.md | covers: scope-guard -->
## `/scope-guard` — a declared blast radius

Lets a repository declare which paths a session may modify, and refuses edits
outside them. Dormant unless you activate it, per runtime.

Reach for it when a session will run unattended, or in a tree where a stray
write is expensive. It is the one guard here that says no rather than advising.

<!-- capability: shortcuts | proof: commands/nr.md | covers: nr av -->
## `nr` and `av` — two instruction overrides, pulled on demand

`$nr <question>` answers one question immediately: no tools, no subagents, no
work trace, no review gates. It suspends the machinery for a single turn, never
the gates that govern doing work. If the answer is not already known it says so
and names what would have to be checked, rather than guessing.

`$av <task>` restates the engineering-lead stance — decide and finish rather
than routing problems upward. Reach for it when a session has drifted into
asking instead of deciding.

Both are triggered by the literal token at the start of your message, never
inferred. On Codex they install as skills you ask for by name, because Codex has
no typed commands.

<!-- capability: orchestration | proof: commands/orchestrator.md | covers: orchestrator build plan reviewer -->
## The orchestrator — OpenCode's reviewed delivery flow

A primary agent that runs substantial work through gates: a brief, a fresh
reviewer, a milestone plan, another reviewer, then execution in reviewable
pieces with a separate final review. `build`, `plan` and `reviewer` are the
agents it drives.

Reach for it when the work is large enough that getting the frame wrong is
expensive. Skip it for a local, obvious, reversible change — the flow says so
itself, and returns a fast path instead.

<!-- capability: workers | proof: agents/worker-qwen-coder.md | covers: worker -->
## The worker agents — one job, many models

Subagents that do bounded work in a fresh context and report back briefly. Their
rules are written once in `shared/roles/` and composed into each definition by
`shared/scripts/build-agents.py`; a gate fails if a shipped file and its source
disagree.

Reach for one when the work is substantial and self-contained, and a fresh
context is worth more than the cost of briefing it. Never for a trivial local
edit: the briefing costs more than doing it.

The model is a frontmatter field, not the agent's identity. Pick the tier the
job needs, and never a cheaper one to save money — the cheap wrong answer is
the expensive one.

<!-- capability: migrate | proof: commands/migrate-check.md | covers: migrate-check migrate-from-cc -->
## `/migrate-check` — moving a repository to OpenCode

Reports what a repository configured for Claude Code would need in order to run
under OpenCode, and what will not carry over. The `migrate-from-cc` skill does
the move.

Reach for it before assuming a repo works in both, not after.
