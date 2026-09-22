---
status: active
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

Item 0 and item 2 are shipped, in commit `05dce52`. Item 1 is designed and
unbuilt; item 4 is decided and unbuilt.

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

## 1 — The agent layer: rules to roles, the model out of the name

### What is there, counted

23 agent definitions, 2281 lines: 3 under `claude/agents/`, 20 under
`opencode/agents/`. Of those 2281 lines, **89 are model- or provider-specific
and 2192 are generic rules for a job** — 3.9%. `opencode/agents/orchestrator.md`
names no vendor anywhere in its 106 lines outside frontmatter.

The 89 is a judgement applied by one reader with a disclosed method, not a
measurement: it counts the `description` and `model` lines, `temperature` where
present, model-named headings, and a handful of capability sentences. Roughly
half of it is the two frontmatter fields. A plain grep for vendor names gives
70-71 instead. The conclusion does not turn on the exact figure — at any of
these counts the generic share is above 96% — but the number should not be
quoted as though it were counted by a script, the way the 836 above is.

By job rather than by name, one job dominates: **17 of the 23 files are
"write code / execute mechanically"**. Planning has one file, dedicated
reviewing one, orchestrating two. Two are genuinely ambiguous and should be
decided rather than forced: `claude/agents/worker-opus.md` mixes judgment with
a conditional reviewing duty, and `claude/agents/worker-fable.md` is scoped by
model difficulty rather than by job at all.

### The drift is systematic, not incidental

Three whole blocks — `## Proportional execution` (14 lines), `## Report budget`
(15) and `## Delivery contract` (15) — are copied into all 19 worker files.
**That is 836 of the 2281 lines, 37% of the agent layer, written nineteen
times.** Hashing each block per file gives one hash for the first two across
all 19, and for the third 18 identical plus `claude/agents/worker-sonnet.md`,
which adds a paragraph:

```
for blk in "## Proportional execution" "## Report budget" "## Delivery contract"; do
  for f in claude/agents/worker-*.md opencode/agents/worker-*.md; do
    awk -v b="$blk" 'index($0,b)==1{on=1;next} on&&/^## /{exit} on{print}' "$f" | md5sum
  done | sort | uniq -c
done
```

All three are **absent from the four role-named files** (`orchestrator`,
`build`, `plan`, `reviewer`), which restate parts of them in their own words —
so the four agents that lead the work are the ones missing the report and
delivery discipline. Meanwhile the rules that carry the most weight exist in
only one runtime:

| Rule | 3 Claude workers | 16 OpenCode workers | 4 role-named |
|---|---|---|---|
| "Never fabricate a confirmation" | all three | **none** | none |
| "The code wins over the doc" | all three | **none** | none |
| English for every artifact | all three | **none** | none |
| "If you can name the check, run it" | **worker-sonnet only** | none | none |
| `Verified:` slot | one wording | a second wording (15), a third (`mistral-fast`) | absent |

The `Verified:` slot reads three ways across the kit. A worker on OpenCode is
not told the code wins over the doc. This is the kit breaking, in its own
files, the rule cs-kernel's charter states for clones: a capability shared by
two or more consumers lives in one place and is never copied.

### What each runtime can actually do

Settled from each runtime's own documentation, and for Claude Code by test.

**Can shared rule text be written once and reach an agent?**

- **Claude Code — yes, preloaded.** `skills:` frontmatter injects the full
  SKILL.md body at subagent startup. Verified by probe rather than read: a skill
  carrying a codeword found nowhere else, and an agent whose `tools:` is `Bash`
  alone so it has no Skill tool and cannot fetch anything, returned the codeword
  after **zero tool calls**. The probe was then re-run with the control it
  lacked — a second agent, identical but with no `skills:` field, answered
  `NO-CODEWORD-IN-CONTEXT`. Without that control the probe showed only that the
  codeword arrived, not that `skills:` is what carried it.
- **OpenCode — not in the form this kit ships, and this was run rather than
  read.** `opencode debug agent <name>` prints an agent's resolved
  configuration without calling a model, so all three routes were tested
  directly on the installed 1.17.18:

  | What was tried | Resolved `prompt` |
  |---|---|
  | `prompt: "{file:…}"` in **markdown frontmatter** | discarded; the prompt is the file body |
  | `prompt: "LITERAL-STRING"` in **markdown frontmatter** | discarded too — so this is not about `{file:}` |
  | `{file:…}` in the **markdown body** | kept **literally** — the model receives `{file:../shared-rules.txt}` as text |
  | `prompt: "{file:…}"` in **`opencode.json`** | **expands correctly** — the shared file's content is the prompt |

  Read together, those rows say something sharper than "`{file:}` does not
  expand". The second row is a control with no `{file:}` in it at all, and it is
  discarded just the same: **markdown agent frontmatter has no `prompt:` field**,
  and the body is always the prompt. That is exactly the documented five-field
  schema — `description`, `mode`, `model`, `temperature`, `permission` — behaving
  as documented, with `prompt:` and `{file:}` belonging to `opencode.json` only.
  There is no include to reach for and no expansion to rely on. The kit ships 20
  markdown agents to
  `~/.config/opencode/agents/*.md` (`install.sh:326,330`), ships no
  `opencode.json`, and no agent of its own uses `prompt:`. Its Agent Skills are
  a separate, explicitly on-demand mechanism — which cannot carry rules
  described as non-negotiable, since the agent must choose to load them.
- **Codex — no preload into an agent's own instructions.** Skills are on-demand
  by name, and `developer_instructions` is an inline string. The config
  reference does carry file-valued keys — `model_instructions_file`
  (`string (path)`, "Replacement for built-in instructions instead of
  `AGENTS.md`") and `experimental_compact_prompt_file` — so "no file mechanism
  at all" would be wrong; but replacing the built-in instructions is not
  including shared text into one agent, and whether that key is honoured inside
  a custom agent file is unverified. `AGENTS.md` is layered per directory, so it
  reaches every agent in the tree and none can opt in or out
  (learn.chatgpt.com/codex/build-skills, /codex/config-file/config-reference).

**Can the caller choose the model per invocation?**

- **Claude Code — yes.** Per-invocation `model` outranks the definition's
  frontmatter; `inherit` is a valid frontmatter value.
- **OpenCode — partly.** An unset subagent model takes the invoking agent's.
  `-m/--model` exists, but as a session flag listed beside `--agent`
  (opencode.ai/docs/cli), not a per-spawn parameter. Which wins when a named
  agent pins a model *and* the caller passes `-m` is **not stated anywhere in
  the documentation** and is not asserted here.
- **Codex — inverted.** "If a custom agent file sets model … the value in the
  file takes precedence" — over the caller's spawn value. A pinned model
  **defeats** the override (learn.chatgpt.com/codex/agent-configuration/subagents).

### The design that follows

**The filename names the role. The model stays a field, and it stays set.**
The requirement is that a model is not an agent's identity — not that no
definition may name one, and the difference decides whether the change is an
improvement or a silent downgrade.

Pinning nothing looks tempting and is wrong here. On Claude Code an unset model
falls back through `CLAUDE_CODE_SUBAGENT_MODEL` to the main conversation's
model, and this kit deliberately runs that conversation on Haiku
(`docs/model-router.md:20-22`). A judgment role with no model would therefore
resolve to Haiku exactly in the sessions the router is designed for — the
cheapest model silently taking the hardest job. The kit's own rules call that a
bug rather than an optimisation: "Picking a cheaper/smaller model to 'save
cost' … If unsure, use Opus" (`AGENTS.md`, Planning). Nothing about renaming
files justifies introducing it.

So each role definition carries the tier its job needs:

- **Claude Code** — keep `model:` in the definition. It is a *default*, not a
  pin: a per-invocation `model` outranks it, so the caller can still choose and
  a caller who names nothing gets the right tier anyway. Strictly better than
  leaving it unset; there is no case where unset wins. "Outranks" is not
  "always honoured" — the installed binary carries `override_dropped`,
  `family_step_down` and an allowlist fallback that inherits the parent model —
  so the definition's value is the floor that matters, which is the argument for
  setting it.
- **OpenCode** — keep `model:` too, and treat it as binding, because whether
  `-m` overrides a named agent's own field is not documented. Choosing the
  safe reading costs flexibility the kit does not currently use.

What actually moves is the **vocabulary**: the role's name and its
`description` stop advertising a vendor and start stating the job and the tier
it requires. That is what the delegating session reads, and it is the thing that
has to change for a model to stop being an identity.

**The shared rules are written once per role, and reach each runtime the way
that runtime allows — which is not the same way twice.**

- **Claude Code — a real include.** The rules live in a skill, and each role
  names it in `skills:`. Nothing is duplicated and nothing is generated.
- **OpenCode — generated, because it has no include.** For a markdown agent the
  body IS the prompt, and neither `prompt:` nor `{file:}` is documented for that
  form. So the role's shipped `.md` is **composed** from the shared rules plus a
  per-role header, by a generator in this repository, and the result is
  committed. The installer keeps copying files whole; the composition happens
  before it, where a reviewer can see the diff.

That generator is the one piece of new machinery in this item, so it owes an
account of what it was chosen over. Two alternatives were considered and
rejected.

**Convert the kit's OpenCode agents to `opencode.json`,** the one form where
`prompt: {file:}` is documented and, as the table above shows, actually works.
Rejected on the kit's own shipping model: `add_one` (`install.sh:266-269`)
appends a source and a destination and copies whole files. A JSON conversion
would require the installer to **merge** its agents into whatever
`opencode.json` a user already has, rather than place a file — strictly more
new machinery than a generator, and machinery that can damage a user's existing
config. The generator extends how this kit already ships; the conversion
replaces it.

**Put `{file:}` in the markdown body and rely on it anyway.** Rejected, and the
test above is the reason rather than a principle. It does not expand: the agent
would ship with the literal string `{file:../shared-rules.txt}` as its entire
prompt — a worker with no rules at all, failing **open**, with no error at
install time and none at run time. That is precisely the failure this item
exists to end. It generalises: this kit installs onto other people's machines
at OpenCode versions nobody here controls, so "it worked when someone ran it"
is not a foundation, and an undocumented behaviour that fails silently is worse
than one that fails loudly.

`install.sh` itself cannot compose — it stamps, renders and substitutes
nothing. The cost of the generator is a committed file that must never be
hand-edited, so it ships with a gate that fails when a generated file and its
source disagree. Without that gate the drift this item exists to end simply
returns in a new place.

**Codex is not in this item, and the reason is not a judgement call.** The kit
ships no Codex agent definitions at all — `codex/` contains six skills and one
hook script, and there is no `.toml` agent file anywhere in the repository. So
there is nothing on Codex for a shared-rules mechanism to reach. Codex's
capability answers above are kept because they decide what happens *if* the kit
ever ships Codex agents: a pinned model would be binding there, and its
instructions field takes no include, so those files would have to be composed
too. That is a different item, on the day it exists.

**Adding a model costs zero new files.** A model is named at delegation time,
so the catalogue is a runtime question, not a file-per-model question. Today
`llms.md` carries a hand-maintained 30-line price and roster table that already
admits a gap (`docs/harness-backlog.md:6-10`), and every shipped agent pins a
static slug. `opencode/agents/worker-auto.md` is the one dynamic precedent, and
its dynamism is entirely external — OpenRouter picks server-side; nothing here
fetches a catalogue.

### The router: what actually couples

No code selects a model from a worker's name. `claude/scripts/router-hook.py`
resolves and prints this session's memory-file path and nothing else, and
`claude/commands/router.md` is an install-and-flag lifecycle. The routing
decision is made by the session model, and the contract reaches it "from the
managed `CLAUDE.md` and from each worker agent's own `description`"
(`docs/model-router.md:20-27`).

So the coupling is **vocabulary, not selection logic**: a session picks a model
by choosing a `subagent_type` whose name and description say which model it is.
What has to change is the delegating session's decision procedure, which lives
in the managed `CLAUDE.md` and in 23 `description` fields — not a parser. That
is why this is one job and not four, and it is cheaper than the plan first
assumed.

One qualification, because "no code reads a worker name" is too strong as a flat
statement. `install.sh:93-95` counts `worker-*.md` and strips the `worker-`
prefix off each filename to print "N worker models — sonnet opus …" in its own
`--list` output, and `install.sh:325,330` iterate the four role names literally
and the worker files by glob. That is display and file placement rather than
model selection, but it is a filename being read as a model name, and all three
loops move when the files are renamed.

### Blast radius, counted

**26 files** mention a worker name. Four are the agent definitions themselves;
of the remaining 22, **12 are live** and 10 are historical briefs and plans that
record what was true then and must not be rewritten. The file count is the
durable half: a line count is self-referential here, since this plan is one of
the 26 and every edit to it moves the number. The live
set, all twelve named: `install.sh:300`, `shared/commands/doc-start.md:20`,
`shared/commands/doc-end.md:12,14-15,58`, the two Codex `WORKFLOW.md` mirrors,
`docs/model-router.md:23-24`, `docs/documentation-harness.md:17-18`,
`docs/harness-backlog.md:34`, `docs/known-issues-and-solutions.md:16,38,39`,
`tests/test_router_install.sh:18,22,28,54,55,69`,
`tests/test_agent_profiles.sh:127-131`, and **`llms.md`**.

`llms.md` is the one to watch. It is installed to `~/.config/opencode/llms.md`
(`install.sh:324`) and read by the orchestrator at every worker pick, and its
table is keyed by worker name — `| worker-glm |`, `| worker-qwen |`,
`| worker-mistral-fast |` (`llms.md:23-27`). A rename that misses it leaves the
orchestrator choosing from a table of names that no longer exist. Both test scripts pass at HEAD and both
would abort on the first hardcoded old name — `set -euo pipefail` stops them
before later assertions run, so a rename must land with them.

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

Item 1 next, as one piece of work rather than four. Its milestones, in dependency
order:

1. **The shared rules, extracted once — BUILT.** `shared/roles/`: `common.md`
   (the non-negotiables, proportional execution, the delivery contract),
   `worker-report.md` (the budget and the report format, for the roles that
   report to a delegating session), one file per role, and a `README.md` that
   states how each runtime consumes them and that a generated file is never
   hand-edited. 245 lines standing in for the 2192 generic ones.

   Three rules were dropped in the first pass and restored after a coverage
   check against the source files — "No comments in code unless asked", "Test in
   the real environment", "Do not delegate". That check is the milestone's real
   verification: a silent drop here would be the regression this item exists to
   prevent, wearing the costume of a refactor.

   Nothing consumes these files yet, which is the point: `grep -rn shared/roles`
   finds no consumer, `tests/test_router_install.sh` and
   `tests/test_agent_profiles.sh` are both exit=0, and `doc-check.py` is
   mechanically clean.

   **Milestone 1 is an extraction, and holding it to that took three rounds.**
   Nothing is lost: the first coverage check matched phrases from a list the
   author had written — circular, and it missed `worker-sonnet`'s "preserve
   content you are asked to move". It is replaced by a mechanical sweep that
   pulls every bolded rule out of all 23 sources and checks each: 13 distinct
   rules, all present. `reviewer.md:32-35`'s "reuse credible verification" was
   absent from both `shared/roles/` and the managed template, so the extraction
   would have deleted it from the kit outright; it is restored.

   Nothing is gained either, but that claim was false when first made and is
   worth recording as such. Three pieces of text had no source in this
   repository: a re-verification rule in `orchestrate.md`, eleven lines in
   `verify.md` about citing `path:line` and about "not verified" differing from
   "not reachable", and an expansion of the English rule beyond its one-line
   original. All three came from outside the kit — the operator's session
   instructions and the meta-repository's own plans — and all three are now
   removed from the extraction and proposed below instead. A fourth was found at
   the last gate and simply deleted — a clause of rationale hanging off a
   sourced imperative in `verify.md`, imposing nothing, but unsourced all the
   same. `shared/roles/` now contains no text without a source in this
   repository.

   The pattern is worth naming: text absorbed from the surrounding conversation
   reads as though it belongs, which is exactly why an extraction needs a sweep
   rather than a memory. Three separate checks missed these — two written from
   the author's own lists, and one whose `grep` exclusion pattern did not match
   the paths `grep` was emitting.

### Proposed, not extracted — decide as its own change

Three pieces of text were written into `shared/roles/` during extraction and
then removed, because a rule change wearing a refactor's costume is the thing
this item exists to stop. They belong together: all three are about not acting
on a claim nobody checked.

1. **Re-verify a worker's or a reviewer's blocking finding at source before
   repairing on it.**
2. **A claim about a file carries a `path:line`, or it is not made** — citing
   does not make a claim true, but reaching for the citation forces the file
   open, which is where the error dies.
3. **"Not verified" and "not reachable from here" are different statements and
   must not share a phrase** — the first is work not done, the second work that
   cannot be done from here.

The evidence for it is this session. Every blocking finding raised here was
re-checked at source before being acted on, and that check changed the outcome
twice: a worker's "the router does not select any model, ever" was true of one
script and false of the system, and the same habit caught two of the author's
own overclaims. It also has a cost — re-checking a finding is work — and the
kit already carries the opposing economy in "reuse credible verification, do not
mechanically replay". The two are compatible (one is about re-running checks,
the other about acting on unchecked claims) but the tension is real and the
wording has to hold both. Decide it as its own change.
2. **The roles, on Claude Code.** Role definitions that include the shared file
   the way Claude Code includes it, verified with a probe of the kind already run
   rather than by reading the frontmatter back.
3. **OpenCode**, via the generator — all twenty of its agent files. The
   sixteen workers are where the copied blocks live; the four role-named ones
   are where those blocks are missing, so both halves are fixed by the same
   move. This milestone carries the new machinery, so it ships with the gate
   that fails when a generated file and its source disagree. Codex has no agent
   definitions, so it has no milestone here.
4. **All twelve live references in the same change** — two of which are the
   test scripts. Both scripts abort on the first stale name, so they land with
   the rename or the rename is not finished. `install.sh:93-95,325,330` moves
   with them, and so does `llms.md`.

Item 4 (the hook guard) follows, in its own session and with its own verification:
it runs in every session on this machine, and the Codex and OpenCode halves of its
injection question are still unanswered.

## What this plan does not establish

The preload question is answered for each runtime, and the router question with
it. Both are stated in item 1 with their evidence, and neither is open.

What remains unestablished:

- **Two of the three runtimes were executed; Codex was not.** On Claude Code a
  probe established the `skills:` preload and, separately, the Haiku fallback.
  On OpenCode 1.17.18 `opencode debug agent` resolved three real agent
  definitions and produced the table above. Every **Codex** claim rests on
  documentation read today and nothing else — codex-cli 0.155.1 is installed
  and was not exercised.
- **Neither runtime's model precedence was tested**, on any binary. The
  OpenCode `-m`-versus-pinned-`model:` question and Codex's inverted precedence
  are both documentation claims here.
- **The OpenCode result is one version's behaviour.** On 1.17.18 a markdown
  agent's frontmatter `prompt:` is ignored — with or without `{file:}` — and
  `{file:}` in the body is passed through literally. That is what this machine
  does today, not a guarantee about the versions the kit installs onto, which is
  itself part of the argument for generating rather than depending on it.
- **`model_instructions_file` is unverified inside a Codex custom agent file**,
  and it replaces built-in instructions rather than including shared text, so it
  is named above rather than used.
- **OpenCode's `-m` precedence over a named agent's own `model:`** is not stated
  anywhere, and this plan does not assert an answer — it chooses the safe
  reading instead.
- **The 89-line split is a disclosed judgement, not a script.** The 836 figure
  ships the command that produces it; the 89 does not, and is worth roughly
  70-71 under a plain vendor grep.
- **Only Claude Code is shown to inject text from a hook.** The Codex and
  OpenCode halves of item 4 are open.
- **This plan does not re-verify the investigation that produced it**: those
  findings carry the record of three review gates, not a fresh check here.
