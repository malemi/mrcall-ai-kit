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
the other machine, or after an install, to see what landed. It reports the
Claude router's persistent flag and registration state. When the re-read hook
script is installed, it also reports that guard's persistent flag and
registration state. This does not prove a hook executed in the client.

<!-- capability: sc | proof: commands/sc.md | covers: sc -->
## `sc` — a re-read pass over one answer

Reach for it when an answer needs a deliberate check against the installed
checklist: an explanation, a design decision, or a short answer where wording
matters. The checklist is `~/.config/mrcall-ai-kit/reread-checklist.md` and you
can edit it.

On Claude Code, `/sc <question>` arms a Stop hook. For an answer of at least
`SC_MIN_CHARS` characters (500 by default), the runtime hands the finished
answer back once with the checklist before delivery. A shorter answer skips
the pass and spends the one-shot arming. `/sc on` and `/sc off` control the
persistent mode on Claude Code only.

On OpenCode, `/sc <question>` inserts the installed checklist into the prompt
and instructs the model to re-read its answer in the current turn. On Codex, ask for the `$sc <question>`
skill to do the same. Both include short answers. Their pass depends on the
model following the instruction; neither runtime offers the Claude Stop-hook
guarantee or an always-on mode.

<!-- capability: router | proof: commands/router.md | covers: router -->
## `/router` — cheap session, expensive workers

The operator chooses the conversation model; the router is designed for a
lower-cost primary session that delegates substantial work to role agents.
`/router on` activates its session-memory hook, and `/router off` stops it.

It names a shared memory path under `docs/sessions/` and instructs the routed
session to create and use that file across delegations. A subagent starts with
an empty context, so the file carries context the next worker needs.

Reach for it on long sessions with a lot of mechanical work in them. Not for a
single hard question, where the delegation costs more than it saves.

`/router sweep` lists open session files with their start time and a transcript
recency label, so you can spot ones a dead session left behind. It never
closes one itself.

<!-- capability: scope-guard | proof: commands/scope-guard.md | covers: scope-guard -->
## `/scope-guard` — protect marked Markdown documents

The opt-in guard is designed to intercept supported file edits to a Markdown
document with an inline `doc-scope` declaration, deny the first attempt, and
present the declaration before an eligible retry. A Claude Code main-session
`Edit` has been verified; other runtime paths remain unverified. Shell writes
and other unhandled tools can bypass it.

Reach for it when an agent may edit declared documents and you need a scope
check on a verified tool path. It installs dormant until activated for that
runtime.

<!-- capability: shortcuts | proof: commands/nr.md | covers: nr av -->
## `nr` and `av` — two instruction overrides, pulled on demand

`$nr <question>` answers one question immediately: no tools, no subagents, no
work trace, no review gates. It suspends the machinery for a single turn, never
the gates that govern doing work. If the answer is not already known it says so
and names what would have to be checked, rather than guessing.

`$av <task>` restates the engineering-lead stance — decide and finish rather
than routing problems upward. Reach for it when a session has drifted into
asking instead of deciding.

Invoke either with its literal token at the start of your message or ask for
it explicitly by name. Neither is inferred from a plain task. On Codex they
install as skills, because Codex has no typed commands.

<!-- capability: orchestration | proof: commands/orchestrator.md | covers: orchestrator build plan reviewer -->
## The orchestrator — OpenCode's reviewed delivery flow

A primary agent that runs substantial work through gates: a brief, a fresh
reviewer, a milestone plan, another reviewer, then execution in reviewable
pieces with a separate final review. `build`, `plan` and `reviewer` are the
agents it drives.

Reach for it when the work is large enough that getting the frame wrong is
expensive. Skip it for a local, obvious, reversible change — the flow says so
itself, and returns a fast path instead.

<!-- capability: workers | proof: agents/execute.md | covers: execute verify reviewer -->
## The role agents — one job each

Subagents that do bounded work in a fresh context and report back briefly:
`execute` carries out work whose decisions are already made, `verify` judges
whether something is actually true, and `reviewer` runs a lifecycle gate. Their
rules are written once in `shared/roles/` and composed into each definition by
`shared/scripts/build-agents.py`; a gate fails if a shipped file and its source
disagree.

Reach for one when the work is substantial and self-contained, and a fresh
context is worth more than the cost of briefing it. Never for a trivial local
edit: the briefing costs more than doing it.

An agent is named for its job. Claude Code and OpenCode get a model field from
the kit's budget resolution. Codex gets the same role instructions in custom
agents and inherits the session model. Pick the role the job needs, and never
a cheaper one to save money — the cheap wrong answer is the expensive one.

<!-- capability: ai-budget | proof: commands/ai-budget.md | covers: ai-budget -->
## `/ai-budget` — how much the role agents may cost

One knob for Claude Code and OpenCode on this machine: `low`, `medium` or
`high`. For every role and budget on those runtimes, the kit has chosen a model
under the budget's price ceiling when possible. A role can be marked below
its score floor when no qualifying candidate is available; `/ai-budget low` switches the installed
agents to the low choices, and so on. With no argument it shows the budget and
each agent's model. A machine that never runs it runs medium.

`high` sets no ceiling. Roles with a `maximise` rule take the highest-scoring
candidate; roles with a `satisfice` rule take the cheapest qualifying candidate.

Reach for it when the bill matters more than the last point of capability, or
the other way round. Never to pick a model: there is none to pick. When a chosen
model disappoints, the recourse is the budget, or a change to the role's
requirements in the kit.

Claude Code uses the new models from its next delegation, in sessions already
open too. OpenCode reads its agents when it starts, so a running OpenCode keeps
its models until it is restarted.
Codex roles inherit the session model; this budget switch does not change it.

<!-- capability: migrate | proof: commands/migrate-check.md | covers: migrate-check migrate-from-cc -->
## `/migrate-check` — moving a repository to OpenCode

Reports what a repository configured for Claude Code would need in order to run
under OpenCode, and what will not carry over. The `migrate-from-cc` skill does
the move.

Reach for it before assuming a repo works in both, not after.
