---
status: planned
---

# Making the kit better: the agent layer, and issues you can see

Date: 2026-09-22
Perimeter set by the CTO: `mrcall-ai-kit`, with the goal of the best kit we can
build. Three runtimes are in scope — Claude Code, Codex, OpenCode — across more
than a hundred models.

Origin: a read-only architecture investigation in the meta-repository
(`hb/docs/briefs/2026-09-21-shopify-engine-starchat-architecture-assessment.md`)
and the conversation that followed it. That investigation's own follow-ups live in
`hb/docs/execution-plans/2026-09-22-post-investigation-followups.md`; this plan is
the kit half and does not repeat them.

Nothing here is implemented yet except item 0. No commit has been made.

## 0 — Done: worker-sonnet aligned with its siblings

`claude/agents/worker-sonnet.md` was missing two rules that `worker-opus.md` and
`worker-fable.md` both carry — "Never fabricate a confirmation" and "The code wins
over the doc" — and its `Verified:` slot lacked "or why a claim stayed
unverifiable". The worker used for mechanical source tracing had the weakest
defences against stating something it had not checked, which is backwards.

Added, plus one rule that is new to all three and belongs to them: **if you can name
the check, run it.** Naming a check you did not run is evidence you knew how, and
"this would have to be verified" belongs only to something out of reach, never to
something a command away. That rule exists because the failure it describes happened
twice in one session, in the delegating session rather than in a worker.

## 1 — The agent layer: rules to roles, model to the caller

The problem, in numbers at today's tree. There are nineteen agent definitions:
three under `claude/agents/` named after models, and sixteen under
`opencode/agents/` also named after models, against four named after jobs (`build`,
`plan`, `reviewer`, `orchestrator`). The sixteen total 1627 lines. In a
representative one, `opencode/agents/worker-qwen-coder.md` at 107 lines, about five
lines are model-specific — the description, the provider string, the temperature —
and the remaining hundred are generic rules for the job of writing code.

They have already drifted, which is the point rather than a detail. The Claude
workers require "never fabricate a confirmation" and "the code wins over the doc";
the OpenCode coder has neither. The `Verified:` slot reads three different ways
across the kit. This is the kit breaking the rule cs-kernel's charter states for
clones: a capability shared by two or more consumers lives in one place and is never
copied.

What to build instead:

- **Roles are the identity.** An agent is a job — writing code, verifying a claim,
  planning, reviewing — and its rules live there, written once.
- **The model is a parameter.** Claude Code's documented precedence confirms a
  per-invocation `model` overrides the definition's frontmatter, and `inherit` is a
  valid value, so a default can stay in the definition while the orchestrator
  chooses per task. Adding a model must cost zero new files.
- **The catalogue is fetched, not stored.** Prices and availability change daily, so
  the orchestrator asks what is available and what it costs at delegation time. The
  kit already has a precedent for dynamic selection in
  `opencode/agents/worker-auto.md`.
- **Shared rules go in a skill.** Claude Code's `skills:` frontmatter field preloads
  a skill's full content into a subagent at startup, which is an include in all but
  name, and skills are the one artifact type all three runtimes accept. Includes
  proper do not exist: the documentation states no include mechanism for agent
  definitions.

Unverified, and it decides how much of this generalises: whether OpenCode and Codex
preload a referenced skill the way Claude Code does. Codex's only install
destination is a skills bucket and its skills are invoked on demand by name, which
is weaker than preloading. Settled by each runtime's documentation, not by this
repository's files.

The coupling to handle carefully: the model router selects a model **by naming a
worker** (`docs/model-router.md`). When workers stop being named after models, the
router's mechanism changes shape. That is a redesign, not a rename, and it is the
reason this item is one job rather than four.

Blast radius, counted: twenty-two files mention the worker names, of which about ten
are live — `install.sh`, `shared/commands/doc-start.md` and `doc-end.md`, their two
Codex mirrors, `tests/test_router_install.sh`, `tests/test_agent_profiles.sh`,
`llms.md`, `docs/model-router.md`, `docs/documentation-harness.md`. The rest are
briefs and execution plans that record what was true then and must not be rewritten.

## 2 — Known issues you can actually see at session start

`doc-start` loads the smallest high-signal context and never reads a known-issues
file, because nothing in the harness does: the command never mentions the directory,
`doc-critic` never mentions it, `doc-end` cites it only as a historical example of a
document split, and the mechanical gate has no check on it. A filed incident is read
when somebody goes looking, and the evidence that this is not enough is in the
meta-repository: three mismatches between an engine's documentation and its code sat
recorded and unrepaired until an unrelated trace walked past them.

The fix follows a mechanism the command already has. It reads plan frontmatter —
`docs/execution-plans/**/*.md` and nothing else — reports `planned`, `active` and
`blocked` as open, and never opens a plan body. Known issues get the same treatment.
Four steps, in order:

1. **Give known-issues files a `status:` frontmatter.** In the meta-repository none
   of the thirty-one files has any frontmatter at all; status appears as prose in
   some and not at all in others, and the index table carries date and incident with
   no status column. Where a file states its status in prose, extract it; where it
   does not, write `unknown`, which surfaces as open and is the safe direction.
2. **`doc-start` scans that frontmatter** exactly as it scans plans, and its summary
   line gains an open-issues count. No body is read, so the cost is one scan.
3. **Mirror the change into `codex/skills/doc-start/WORKFLOW.md`**, or the runtimes
   diverge again in the same command.
4. **The gate reports before it enforces.** For plans a missing status is already a
   mechanical violation. Doing that immediately for known issues would fail the gate
   in every repository whose issues have no frontmatter, so this is advisory first
   and enforced only once the repositories have caught up.

## 3 — The two texts from the investigation, awaiting a decision

The investigation proposed, and an independent reviewer approved over seven rounds,
two pieces of text for this kit: a five-line boundary note for briefs whose change
crosses a boundary someone else owns, and one section in `shared/templates/CLAUDE.md`
requiring work to state what it does **not** establish, with a reviewer clause making
a conclusion that contradicts that statement a `REVISE`.

It recommended **against adopting them**, on the ground that one in-scope incident is
not a basis for changing how everyone works, and named the evidence that would settle
it: for each brief, record where an overclaim was first caught — the author's own
statement, a reviewer, or the owner. That recommendation was a judgement about
evidence and not about permission, so widening the perimeter does not overturn it.
The decision is the CTO's and should be explicit rather than arrived at by drift.

## 3b — A second incident on the same gate, from another repository

`124-cs/docs/briefs/2026-09-22-question-class-leak.md` records an operator asked for
a business-model outline that returned a per-contact pipeline review: every step
valid, every figure sourced, and the frame wrong. Its structural finding is verified
here against source — every gate after the brief measures the work **against the
brief** (`claude/agents/worker-opus.md:66-67`), so a frame error in the brief passes
each later gate precisely because the work is faithful to it.

It proposes one sentence for `shared/templates/CLAUDE.md`: that a brief reviewer's
first question is whether the artifact is the right **kind** for the question asked.

This matters for item 3 rather than standing apart from it. The brief gate requires
five things (`:40-41`) and all five are forward-looking descriptions of the work.
Nothing asks whether the artifact fits the question, and nothing asks what a
conclusion failed to support. Two different defects, one weak point, now two
independent incidents from two repositories and two sessions — which is the evidence
item 3 said it lacked, though it does not by itself establish that either proposed
wording would have caught either case.

Decide both together. Two sessions adding one sentence each to the same gate is how a
template accumulates sediment, and the two changes are about the same paragraph.

Attributed and unverified: that brief's account of its own session, including its
claim that the flow caught six real defects there, was not checked here.

## 4 — Enforcement, if hooks are turned on

Both capabilities a guard would need already exist in this kit. `MessageDisplay`
carries the assistant's own text, which `claude/scripts/scope-guard-hook.py` already
consumes; a hook's response carries `additionalContext` alongside its permission
decision, so a hook can inject text and not merely allow or deny. They need not be
the same event: the scope guard already records on one event and decides on another.

The guard worth building is the one this session earned — a session that names a
check it did not run is stopped until it runs it.

**Injection is confirmed, 2026-09-22.** The open question was whether a hook can
put text in front of a session or only allow, deny and ask, because the scope
guard demonstrates interception and not injection. It can: a throwaway
`PreToolUse` hook returning `hookSpecificOutput.additionalContext` was registered
through `claude -p --settings`, and the session reported the injected codeword
unprompted. So the guard is buildable on Claude Code. The same question for the
Codex adapter and the OpenCode plugin is still open, and each has its own answer.

Two prerequisites remain, neither technical. First, hooks are **not running**: the scope
guard is installed and not registered in settings, so turning hooks on at all is a
decision that changes every session on that machine. Second, parity: a Claude hook
script, a Codex adapter and an OpenCode plugin already exist for the scope guard, so
the pattern is there, but Codex's own adapter calls its enforcement "degraded" and
the OpenCode plugin interface has not been read. The precedent proves a hook can
intercept a tool call; it does not prove any of the three can inject text a session
will read.

## Decided by the CTO, 2026-09-22

- **Hooks: yes, and they must be switchable.** Whatever guard is built ships with
  an on/off switch rather than being wired in. The pattern already exists —
  `install.sh` takes `--activate-scope-guard claude|codex|opencode|all`, never
  enables a hook by itself, and the settings schema has `disableAllHooks` — so the
  requirement is to follow it, not to invent it. Item 4 starts from there.
- **The brief-gate sentence is in.** `shared/templates/CLAUDE.md` gate 2 now reads
  that a brief reviewer's first question is whether the artifact is the right
  *kind* for the question asked, because a frame error is invisible to every later
  gate. Eight repositories we own were re-synced to the template in the same pass;
  `starchat` and `zylch-deploy` were left alone, so their gate reports the drift
  until their owners sync them.
- **The other text is still held.** Requiring every work document to state what it
  does not establish stays unadopted: one in-scope incident, already caught by an
  existing gate. The measure that would settle it is unchanged.

## Order

Item 2 first: it depends on no decision, and its four steps unblock each other.
Item 1 next, as one piece of work rather than four, starting with the shared rules
and leaving the router redesign until the roles exist. Items 3 and 4 wait on the two
answers above.

## What this plan does not establish

It does not establish that OpenCode or Codex can preload a shared skill the way
Claude Code does, which decides how much of item 1 generalises rather than applying
to one runtime. It does not establish that any of the three runtimes can inject text
from a hook, which is the capability item 4 depends on and which the existing scope
guard does not demonstrate. It does not establish what the router should become once
workers are no longer named after models, only that its current mechanism stops
working. And it does not re-verify the investigation's own findings: those carry the
record of three review gates, not a fresh check by this document.
