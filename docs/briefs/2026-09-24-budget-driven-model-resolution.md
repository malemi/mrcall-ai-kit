# One knob: a budget, and the kit chooses the models

Date: 2026-09-24
Repository: `mrcall-ai-kit`

## What this is for

An agent should be bound to a **behaviour**, never to a model. Today it is the
opposite: a delegating session picks `worker-sonnet` or `worker-glm`, and the
name *is* the model, so choosing how to work means choosing a vendor and a
price. That choice is made by guessing, it is made again at every delegation,
and it goes stale silently: `llms.md:16-17` lists two of the four orchestrator
models at a price of "? / ?".

What replaces it is one control: `/ai-budget low|medium|high`, default medium.
The operator states an appetite. The kit resolves, for every role and for each
runtime, the model that satisfies that role's requirements at that appetite.
Nobody edits a model name again.

## What the data says

Measured on 2026-09-24. Prices move daily, so every figure below carries its
source and is reproduced by the refresh rather than trusted.

**A quality signal exists.** `GET https://openrouter.ai/api/v1/benchmarks`
needs an OpenRouter key (HTTP 401 without one). Its snapshot is dated
`as_of 2026-09-24T09:11:57Z`: 265 models, 1555 records from three sources. The
154 Artificial Analysis records carry `intelligence_index` (96 of them),
`coding_index` (148) and `agentic_index` (100). `GET /api/v1/models` is public;
it listed 458 entries at 11:33Z, with price, context length and
`supported_parameters`.

**The two endpoints join exactly.** A benchmark record's `model_permaslug`
equals a catalogue entry's `canonical_slug`: 131 of the 154 records match. The
alternative, stripping a date suffix off the permaslug, matches 104 and fails on
the catalogue's own spelling of older models (`anthropic/claude-opus-4.1` has
the canonical slug `anthropic/claude-4.1-opus-20250805`). 56 canonical slugs
belong to more than one entry, and the extra entries are `:batch` (47) or
`:free` (12) variants: a batch route cannot serve an interactive agent, and a
free route is rate-limited. Without variants, 128 entries join, and 101 of those
support tool calling with at least 200k tokens of context.

**Price does not track capability.** `claude-opus-5.5` scores 57.6 on
intelligence and costs $20 per million output tokens. `claude-fable-5.1` scores
53.4 at $50. `claude-opus-4.1` costs $75. A human maintaining these by intuition
gets them wrong in a direction intuition cannot correct.

**Price alone collapses every role onto one model.** Once `:batch` and
`:free` variants are excluded, 197 catalogue entries support tools and
reasoning with at least 200k context. The cheapest paid one is
`inclusionai/ling-3.0-flash` at $0.063, and a price-only rule gives it to every
role alike. Capability data is what separates `verify` from `execute`.

**Coverage is uneven, and new models arrive partly scored.** `claude-opus-5.5`
carries an intelligence score and no coding or agentic score. It can be chosen
for a role ranked on intelligence and is invisible to a role ranked on the other
two until Artificial Analysis publishes them.

**Open weights hold their own.** `moonshotai/kimi-k3` scores 43.6 / 76.2 / 50.0
(intelligence / coding / agentic) at $15; `claude-sonnet-5` scores
38.2 / 71.5 / 43.6 at $10.

## The design

### A role declares requirements, not a model

Requirements are behaviour expressed as constraints, and they are what the
kit's maintainer writes, in `shared/roles/requirements.json`:

| Role | Rule | Ranked on | Floor |
|---|---|---|---|
| `verify` | maximise | intelligence | none |
| `review` | maximise | intelligence | none |
| `plan` | maximise | agentic | none |
| `orchestrate` | maximise | agentic | none |
| `execute` | satisfice | coding | 73, set by the operator |

`verify` and `review` judge claims, so they rank on intelligence. `plan` and
`orchestrate` explore and act through tools over long horizons, so they rank on
agentic. `execute` writes code, so it ranks on coding.

Every role also requires: tool calling; at least 200k tokens of context; a
score on the role's own index and on intelligence, so that any two roles can be
compared on intelligence; and a catalogue entry that is not a `:batch` or
`:free` variant. A model that fails any of these is not a candidate for that
role.

### The budget is a price ceiling, and nothing else

The ceiling is in US dollars per million **output** tokens, as OpenRouter's
catalogue gives it (`pricing.completion`). low and medium each set a ceiling
per runtime; high sets none. One mechanism, no per-budget model lists. The
values are in "What the operator decided" below. The mechanism reproduces the
intent, including the part that is easy to get wrong: high does **not** mean
"spend more". `verify` resolves to `claude-opus-5.5` at $20 under every ceiling
from $20 upwards and under none, because it is the highest intelligence score
available and nothing better exists to buy.

### Two selection rules

- **Maximise**: the highest score on the role's index among candidates priced at
  or under the ceiling. A tie goes to the cheaper model.
- **Satisfice**: the cheapest candidate at or under the ceiling whose score
  clears the floor. A tie goes to the higher score. When nothing clears the
  floor under the ceiling, the role takes the highest score under the ceiling,
  and the refresh marks that choice as below the floor.

Roles where a plausible-but-wrong answer is expensive maximise. The role that
does volume satisfices; without the floor-then-cheapest rule, `execute` spends
the whole ceiling on mechanical work.

When a role has no candidate priced under the ceiling, the refresh raises that
runtime's ceiling for that budget to the lowest price at which every role has a
candidate, applies the same rules under it, and marks the budget as raised.
Raising one ceiling for all the roles keeps every role choosing from the same
price range, so `verify`'s pool still contains `execute`'s pick, and every
choice is still a scored model. A role with no candidate at any price is a
data failure, handled as an unreadable endpoint is.

### Which models each runtime can be given

**Claude Code: Claude's own models only.** The candidates are the catalogue's
`anthropic/*` entries. The resolver writes the Claude model id, which is the
catalogue id's model part with dots replaced by dashes:
`anthropic/claude-opus-5.5` becomes `claude-opus-5-5`. This was run, not read:
four probe subagents whose frontmatter said `model: claude-sonnet-5`,
`claude-haiku-4-5`, `claude-opus-5-5` and `claude-fable-5-1` each ran on exactly
that model, under a session on a different one, as each subagent's own
transcript records. The catalogue's Anthropic prices are list prices. They rank
Claude's models against each other; they are not the operator's bill, which a
subscription decides.

**OpenCode: OpenRouter routes.** The candidates are every catalogue entry that
meets a role's requirements, and the resolver writes them as `openrouter/<id>`.
OpenRouter is the only source that gives a score, a price and a callable id for
the same model. On this machine `opencode models` lists all 101 candidates in
that form.

The consequence is stated rather than left to be discovered: 19 of the 20
OpenCode agents the kit ships call a Zen (`opencode/`) or Scaleway route today,
and only `worker-auto` calls OpenRouter. After this change none of the kit's
OpenCode agents calls Zen, Scaleway or Kimi. An OpenCode without its OpenRouter
provider cannot run them.

Rejected: mapping catalogue entries onto Zen or Scaleway ids. Those routes
publish no price the kit can read, so ranking them needs a hand-kept price
table, which is the maintenance this change exists to remove.

### Where resolution runs, and where its result lives

- **The refresh** is a script in the kit, run in a checkout by the kit's
  maintainer (today the operator) with an OpenRouter key. It reads both
  endpoints, resolves every role for every budget on both runtimes, and prints
  the result as a diff. It writes only when told to. What it writes is one
  committed data file, `shared/roles/models.json`: the selection, and the
  scores, prices and `as_of` it was chosen on. The refresh never runs at
  install, at `/ai-budget`, or at delegation.
- **Rendering.** `shared/scripts/build-agents.py` renders every agent once per
  budget, into committed files, from committed sources only: the stubs, the
  shared blocks and `models.json`. `tests/test_agents_generated.sh` fails when
  any rendering and its sources disagree. The gate stays deterministic because a
  machine's budget is never an input to a committed file.
- **The budget** is per-machine state in the kit's global home,
  `~/.config/mrcall-ai-kit/budget`. When it is absent the machine runs medium.
- **Applying a budget.** `install.sh` installs every budget's rendering of each
  kit agent into the kit's global home, under `~/.config/mrcall-ai-kit/`, and
  places the rendering for the machine's budget where the runtime reads agents.
  Both follow the install mode: links into the checkout in symlink mode, copies
  in copy mode. `/ai-budget <level>` records the level, then re-points or
  re-copies each of those runtime agent files from that level's installed
  rendering. It needs no key, no network and no checkout, and it never writes
  into the checkout. A copy-mode install therefore stays a frozen snapshot: a
  budget switch moves between renderings copied at install time, and never
  pulls in what the checkout holds now.
- **The key.** The refresh reads the OpenRouter key from the
  `OPENROUTER_API_KEY` environment variable and from nowhere else. A shipped
  script never reads another tool's credential store.

### What a delegating session does

A session chooses a role by the job and never names a model. On Claude Code the
`Agent` tool accepts a per-call `model`; the kit's instructions tell a session
not to pass one, and nothing enforces that.

Five texts in the kit tell a session to choose a model, and each is rewritten
to choose a role instead: `shared/roles/orchestrate.md:30-35` ("Raise it at
delegation time"), `shared/tutorial.md:129-131` ("Pick the tier the job needs"),
`docs/model-router.md:20-25` (the router's workers named by model),
`opencode/skills/orchestrator/SKILL.md:102-104` ("Choose capability for the
task", reading `llms.md`), and the kit's own `AGENTS.md:41-42` ("If unsure, use
Opus"). What each says against
saving money stays true of roles: never a cheaper role than the job needs. The
operator's budget is not that saving, because a session never makes it.

There are no pins. A pinned model is a second knob and a model name the operator
writes, and the settled design has one knob and no model names. When a resolved
model disappoints in practice, the recourse is the budget, or a change to the
role's requirements in the kit.

## Milestone one: the rename

The plan written from this brief carries the rename as its first milestone.
That closes the rename half of item 1 in
`docs/execution-plans/2026-09-22-kit-agent-layer-and-issue-visibility.md`, which
designed it and left it unbuilt. There is nothing to attach requirements to
until a delegated agent is a role, so it lands first. Until the first refresh,
each role runs the model of the predecessor named in the table below. Where
several agents collapse into one role, the others' jobs move to that model:
fifteen OpenCode workers' jobs move to `opencode/claude-sonnet-5`, and
`worker-fable`'s to `opus`.

| Today | After | Interim model, until the first refresh |
|---|---|---|
| Claude `worker-sonnet` | `execute` | `sonnet`, as today |
| Claude `worker-opus` | `verify`, and `reviewer` (its "Artifact and integration review" section), role `review` | `opus`, as today |
| Claude `worker-fable` | retired into `verify` | — |
| OpenCode's 16 `worker-*` | `execute` | `opencode/claude-sonnet-5`, the worker `doc-start` and `doc-end` name |
| OpenCode `reviewer` | `reviewer` (name kept), role `review` | `opencode/claude-sonnet-5`, as today |
| OpenCode `plan` | `plan` (name kept) | `opencode/claude-opus-4-8`, as today |
| OpenCode `build` | `build` (name kept), role `orchestrate` | `opencode/claude-opus-4-8`, as today |
| OpenCode `orchestrator` | `orchestrator` (name kept), role `orchestrate` | `opencode/big-pickle`, as today |
| — | OpenCode `verify` (new) | `opencode/claude-opus-4-8` |

Four names are kept. `plan` and `build` override OpenCode's own built-in agents
of those names (`opencode debug agent build` resolves to the kit file's prompt
and model), and `build` is the operator's `default_agent`. `orchestrator` and
`reviewer` already name a job, not a vendor, and `reviewer` is what OpenCode's
lead agents are permitted to call and told to ask. Claude Code's new review
agent takes the same name, so a review is delegated to `reviewer` on both
runtimes. An agent is named for its job; the role it plays is the entry in the
requirements. OpenCode gains `verify` because it has none:
`shared/commands/doc-end.md:12` tells a session there to improvise one.
`worker-fable` retires because its job, the hardest analysis, is `verify`'s, and
under the budget `verify` takes the most capable model the ceiling allows.

**How delegation changes.** On Claude Code, three model-named workers become
three roles. On OpenCode the change is larger: the orchestrator stops choosing
among sixteen models per task. `llms.md:98-124` routes by vision, context
length, languages and a free tier. After the rename, what a role needs becomes a
requirement it declares, resolved once at refresh. Per-task needs the
requirements do not cover, such as image input, are no longer routed.
`worker-auto` is one of the sixteen, and its job is `execute`'s like the rest.
What goes with its file is per-request routing: its model is OpenRouter's
router, which has no score for the resolver to rank. `llms.md` retires too. It
exists for per-task model choice, which ends, and `/ai-budget` shows what each
role runs on.

**An installed machine migrates.** Installing retires the agent files the kit
installed under the old names. A file under an old name is the kit's when the
install manifest records it, or when its bytes equal a version the kit shipped
at that path, which the checkout's history answers
(`git log --all --find-object=<blob> -- <path>`). Anything else under an old
name stays where it is, and the installer reports it. Nothing under any other
name is touched.

Retiring follows `--on-exist`, exactly as replacing does. `overwrite` deletes a
retired kit file, and `backup` moves it to `<file>.bak`. `skip` retires
nothing: it lists the retired kit files it found and says that `overwrite` or
`backup` completes the migration. Under `skip` the kept-name agents are not
replaced either (`install.sh:77-78`), and on this machine the installed
`build.md`, the operator's default agent, may call no kit agent except `worker-*`. It
still names six of the Scaleway workers. Removing the workers while leaving that
file would strand it.

This machine shows why both tests are needed. The manifest records the three
Claude workers and four OpenCode agents. The sixteen OpenCode workers are not
recorded, yet each is byte-identical to a version the kit shipped: fifteen to
`2cf0206`, `worker-auto` to `df40f9a`. `~/.config/opencode/llms.md` matches no
version the kit shipped, so it stays and is reported. Once an `overwrite` or
`backup` install has replaced the orchestrator skill, nothing reads it; the July
copy of that skill still does. The four agents in `~/.config/opencode/agents/` that are not
the kit's are left alone.

## Scope

In: `mrcall-ai-kit`. The rename and every live reference to the old names; the
role requirements; the refresh; `shared/roles/models.json`; per-budget
rendering in the generator; `install.sh`, `uninstall.sh` and the migration;
`/ai-budget` for Claude Code and OpenCode; the tests and the docs these change.

Out: `cs-kernel`, `mrcall-desktop` and the meta-repository. Codex, because the
kit ships no Codex agents, so there is nothing there to resolve. The hook guard,
which is item 4 of the 2026-09-22 plan.

## Constraints

- Generated files are never edited by hand. A change is made in a stub, a
  block, the requirements or `models.json`, and then regenerated.
- The install modes keep their meaning: symlink mode points into the checkout,
  and copy mode is a frozen snapshot.
- Installing, applying a budget, and running any agent on Claude Code need no
  OpenRouter key. Only the refresh reads the benchmarks endpoint, and it reads
  the key from `OPENROUTER_API_KEY` alone.
- Every artifact is in English, and docs describe the present system.
- Every commit lands in `mrcall-ai-kit` alone, staged by explicit path, on
  `main`. Nothing is pushed.

## Acceptance criteria

1. `/ai-budget low|medium|high` sets the machine's budget and applies it to the
   installed kit agents. Without an argument it prints the budget and each
   role's model. A machine that never runs it behaves as medium. Both runtimes
   read their agents when a session starts (`docs/known-issues-and-solutions.md`,
   "does not hot-reload agent files mid-session"), so the command says that a
   switch applies to sessions started after it.
2. No role stub names a model. Every `model:` in a shipped agent file comes from
   `shared/roles/models.json`, and every entry there was written by the refresh.
3. A refresh prints, per runtime, budget and role, the old model, the new model
   and both prices, and changes nothing unless told to apply.
4. Selection follows the table and rules above, including the below-floor
   fallback and the raised ceiling. A fixture-driven test covers each rule.
5. The resolver degrades rather than guesses. An endpoint it cannot read (no
   network, no key, an error) changes nothing, and the refresh says so. So does
   a role with no candidate at any price. A model without a score on a role's
   index is never a candidate for that role.
6. On Claude Code the candidates are Claude's own models, written as Claude
   model ids. On OpenCode they are OpenRouter routes, written
   `openrouter/<id>`. When OpenCode is installed on the refreshing machine,
   every id written for it is one that `opencode models` lists.
7. A test asserts that in every budget and on both runtimes, `verify`'s model
   scores at least as high as `execute`'s on intelligence. It runs on fixture
   data and on the committed `models.json`. That collapse is the failure this
   change exists to prevent.
8. After the rename, no shipped agent, installer line, command, skill, test or
   live doc names a model-named worker or `llms.md`. Historical briefs, plans
   and incident records keep their names. An installed machine migrates as
   described, under each `--on-exist` value, and every gate passes.
9. A budget switch on a copy-mode install changes only which installed
   rendering each runtime agent file is; a test shows it reads nothing from the
   checkout.

## What the operator decided

On 2026-09-24, from the evidence below:

| | low | medium | high |
|---|---|---|---|
| OpenCode ceiling | $5 | $20 | none |
| Claude Code ceiling | $10 | $20 | none |
| `execute` floor, both runtimes | coding 73 | coding 73 | coding 73 |

The ceilings are set per runtime because Claude's lineup has no model between
$5 and $10, and none between $10 and $20 that scores above `claude-sonnet-5`. A
single ceiling that suits OpenCode would put Claude Code on Haiku. The values
live in one committed file the refresh reads, `shared/roles/requirements.json`,
beside each role's rule, index and floor; changing one is an edit and a refresh.

The OpenCode ceilings are OpenRouter prices. Routing every OpenCode agent
through OpenRouter was put to the operator, with its consequences, before he set
them: every OpenCode that runs the kit's agents needs an OpenRouter provider,
and the Scaleway route that `llms.md:19` calls "European sovereign cloud" leaves
the kit's agents.

What the first refresh will resolve, on today's data:

| OpenCode | `verify`, `review` | `plan`, `orchestrate` | `execute` |
|---|---|---|---|
| low | grok-4.7, 46.4, $4.80 | glm-5.3, 53.1, $2.64 | glm-5.3, 74.8, $2.64 |
| medium | opus-5.5, 57.6, $20 | qwen3.8-max-0902, 56.0, $6 | glm-5.3, 74.8, $2.64 |
| high | opus-5.5, 57.6, $20 | fable-5.1, 57.9, $50 | glm-5.3, 74.8, $2.64 |

| Claude Code | `verify`, `review` | `execute` |
|---|---|---|
| low | sonnet-5, 38.2, $10 | sonnet-5, 71.5, $10, below the floor |
| medium | opus-5.5, 57.6, $20 | sonnet-5, 71.5, $10, below the floor |
| high | opus-5.5, 57.6, $20 | opus-5, 78.0, $25 |

Three consequences follow from these values and today's coverage, and they are
the operator's to watch rather than the resolver's to hide:

- On Claude Code, `execute` stays on `claude-sonnet-5` at low and medium, and
  the refresh marks it below the floor every time.
- At high, Claude Code's `execute` moves to `claude-opus-5` at $25, above what
  `verify` costs, because `claude-opus-5.5` has no coding score yet.
- Once Artificial Analysis publishes a coding score of 73 or more for
  `claude-opus-5.5`, Claude Code's `execute` at medium moves to it.

At low on OpenCode, `plan` gets 92% of the best agentic score for one
nineteenth of its price. At high it takes the $50 model, because that model
holds the best agentic score on record and `claude-opus-5.5` has none.

## Material assumptions

- On OpenCode, OpenRouter's prices are the bill, because the routes are
  OpenRouter's. On Claude Code they are an ordering only.
- Artificial Analysis indices are a usable proxy for the behaviour each role
  needs. They are third-party scores, not measurements of this kit's own work.
- The output price stands in for cost. Agentic work reads far more than it
  writes, and the ratio of input to output price differs by model: 1 to 5 for
  Anthropic's, about 1 to 3.1 for `glm-5.3`. The ceiling therefore ranks by a
  proxy for cost, not by cost.

## What this brief does not establish

- **Output quality.** Nothing here measured whether a resolved model does a
  role's job better than the hand-chosen one. That is a claim about output, and
  no output was measured.
- **Coverage over time.** 23 of the 154 benchmark records match no catalogue
  entry, and those models are invisible to the resolver. A new model is
  invisible to a role until its index is published.
- **Enforcement at delegation.** Nothing stops a Claude Code session from
  passing a `model` to the `Agent` tool.
- **Which upstream providers see a prompt.** OpenRouter routes each request to
  one of several hosts. Which hosts are allowed, and their data policies, are
  settings of the OpenRouter account, which the kit does not manage.
- **Other machines.** Reachability is checked against the refreshing machine's
  OpenCode. A machine with a different provider setup is not checked.
- **Codex** is not exercised, and it is out of scope.
