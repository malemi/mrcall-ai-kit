# Where an agent's rules are written

Every agent the kit ships is composed by `shared/scripts/build-agents.py` from
the files in this directory, once per budget on Claude Code and OpenCode, and
once per role on Codex. `tests/test_agents_generated.sh`
fails when a shipped file and its sources disagree. **Never edit a shipped agent
file**: edit a stub, a role, a block or the manifest here, then regenerate.

## The agents

An agent is named for its job. A delegating session chooses a role, never a
model.

| Agent | Role | Runtimes |
|---|---|---|
| `execute` | carries out work whose decisions are already made | Claude Code, Codex, OpenCode |
| `debugger` | traces actual failing data to the first demonstrated divergence; read-only diagnosis | Claude Code, Codex, OpenCode |
| `verify` | judges whether something is actually true | Claude Code, Codex, OpenCode |
| `reviewer` | runs a lifecycle gate: brief, plan, milestone, final | Claude Code, Codex, OpenCode |
| `build`, `orchestrator` | lead the work and delegate to the roles | OpenCode |
| `plan` | plans read-only | Codex, OpenCode |

## What an agent is made of

| File | What it holds |
|---|---|
| `agents/<runtime>--<name>.md` | one stub per agent: its frontmatter, which names no model, and for a lead, its own text |
| `execute.md`, `verify.md`, `debugger.md`, `review.md`, `plan.md` | role text, shared by the runtimes that use it |
| `common.md` | the non-negotiable rules every role shares |
| `block-proportional-execution.md`, `block-report-budget.md`, `block-delivery-contract.md` | the three shared blocks |
| `worker-report.md` | the report format every role returns |
| `agents.json` | each agent's runtime, rendering path, role, and the blocks it carries |
| `requirements.json` | Claude Code and OpenCode role requirements, including ranking rules, score floors, and budget ceilings |
| `models.json` | Claude Code and OpenCode model choices per role and budget, with scores, prices, and dates; written by the refresh |
| `retired.txt` | files the kit once installed and has retired; no other live file may name them |
| `orchestrate.md` | the leading role text; OpenCode leads keep their own text |
| `block-mandate-completion.md` | the decision to yield, composed into Codex global instructions and every generated final-report procedure |
| `codex-lead.template.md` | static source of the generated `codex/AGENTS.block.md`, with one mandate-completion placeholder |
| `reread-checklist.md` | the six re-read rules embedded in every generated agent; also installed as an editable checklist by `--features reread` |

A role agent's file is its stub, then its role text, then what every role
shares. A lead's file is its stub, which carries its own text. Each agent is
rendered once per budget on Claude Code and OpenCode, into
`<runtime>/agents/<budget>/<name>.md`; those renderings differ only in the
`model:` line from `models.json`. Codex profiles are TOML files under
`codex/agents/`, each generated once without a model pin.

Every generated agent receives the decision to yield, the six shipped re-read
rules, and an instruction to check its final report before delivery. The decision
applies to the bounded assignment, including useful authorized work still to do;
accurately reporting incompleteness does not complete that assignment. Claude
Code roles receive them in the preloaded `kit-role-rules` skill; OpenCode roles and leads carry them inline;
Codex roles carry them in `developer_instructions`. Fixed report headers and
the reviewer's verdict position take precedence over the checklist's
answer-first wording. This is a model instruction, not a delivery hook. The
optional `sc` command uses the editable installed checklist; edits to that
copy do not change already generated agents.

## How a model is chosen

No stub names a model. `shared/scripts/resolve-models.py` refreshes Claude Code
and OpenCode choices: it
reads OpenRouter's catalogue and benchmarks, applies `requirements.json` to
them, and prints, for every agent on those runtimes and budget, the model it runs now, the model
the rules choose, and both prices. With `--apply` it writes `models.json`; then
`build-agents.py` renders the agents from it. The benchmarks need an OpenRouter
key, read from `OPENROUTER_API_KEY` only. The refresh never runs at install or
at delegation: an install places the rendering for the machine's budget, read
from `~/.config/mrcall-ai-kit/budget` (medium when absent), and every budget's
rendering in `~/.config/mrcall-ai-kit/agents/`. Codex agents inherit the
session model and are outside this resolver.

`debugger` uses the same intelligence-maximising requirements as `verify`. Its
initial selections reuse the recorded verify choices with per-selection provenance;
future resolver runs select it normally. No fresh catalogue claim is made.

## Diagnostic handoff

Choose `debugger` for a failing case whose cause is uncertain, `execute` for
applying a decided correction, and `verify` for checking consequential claims.
Give the debugger the entry command, expected behavior, actual case data and
evidence paths, revision/environment, authority and resource bounds. It returns
the first demonstrated divergence, causal chain, evidence limits and smallest
next check in the common report; detailed traces belong in authorized scratch.
Codex applies a read-only sandbox; Claude omits edit tools and OpenCode denies
edit. Shell access can still have side effects: these profiles do not enforce
purity for arbitrary diagnostic commands. Product changes and production writes
remain outside this role.

Native Codex CLI acceptance on 2026-10-30 loaded the installed `debugger` in an
isolated persistent session. It reproduced a misleading timeout wrapper around
local string arithmetic, traced the original cause and checked an in-memory
counterfactual in four shell calls, leaving fixture files unchanged. The earlier
`--ephemeral` attempt failed before the child started because no rollout was
available. This establishes one diagnostic sample; Claude/OpenCode native
adherence, production diagnosis and general reliability remain unverified.
The [delivery plan](../../docs/execution-plans/2026-10-30-debugger-agent.md)
records the retained evidence and bounded attempts.

## How each runtime receives the shared parts

**Claude Code has a real include.** `skills:` preloads a skill's full body into
a subagent at startup, so each role names `kit-role-rules` — the rules, the
blocks, the report format, and the re-read checklist — and its file ends at its role text. A personal skill in
`~/.claude/skills/` wins over a project skill of the same name, so a changed
skill can be tried in a project only under another name.

**OpenCode has none**, so its role agents carry the same parts inline, and its
leads carry the re-read checklist inline. A
markdown agent there has no `prompt:` field — the body is always the prompt —
and `{file:}` belongs to `opencode.json`, passing through a markdown body as
literal text in the inspected OpenCode 1.17.18. The documented frontmatter
fields are `description`, `mode`, `model`, `temperature` and `permission`;
`tools:` is honoured too, so treat that list as documented rather than
exhaustive.

**Codex receives composed custom agents.** Their `developer_instructions`
contain the role, common rules, three shared blocks, report format, and re-read
checklist. The
installer places physical TOML files under `~/.codex/agents/`: Codex 0.158.0
rejected the symlink form in a real spawn probe. A global kit block in
`~/.codex/AGENTS.md` tells a fresh lead when to use them. Codex roles inherit
the session model; `/ai-budget` does not switch them.

The generator also composes Codex's global kit block from `codex-lead.template.md`
and `block-mandate-completion.md`; `--check` covers that output. Its installed
`~/.codex/AGENTS.md` entry gives fresh Codex leads the decision independently of
repository orientation. Ordinary Claude leads receive no new global instruction
through this route; their kit
workers receive the decision through `kit-role-rules`. See
[delivery and measured limits](../../docs/reread-guard.md#mandate-completion).

The v9 lead follows the managed root `AGENTS.md` block, personally loading
routing and relevant documentation before source investigation. Bounded role
handoffs carry relevant startup, documentation-impact, and result references;
workers do not reconstruct the lead's transcript. Final reviewers require
current mechanical, explicit critic, coverage, and living-context shape results
for applicable closure. Missing or stale evidence yields `REVISE`. These role
instructions do not supply a runtime final-answer interceptor.

When a handoff names an existing completion task, role instructions use the
optional [verification advisory](../../docs/verification-warnings.md) to inspect
its actual required-command receipts before reporting them verified. Notifications
need an explicit native session binding; warnings do not block a session or
replace completion gates. This instruction does not classify report prose.
