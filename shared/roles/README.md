# Where an agent's rules are written

Every agent the kit ships is composed by `shared/scripts/build-agents.py` from
the files in this directory, once per budget, and `tests/test_agents_generated.sh`
fails when a shipped file and its sources disagree. **Never edit a shipped agent
file**: edit a stub, a role, a block or the manifest here, then regenerate.

## The agents

An agent is named for its job. A delegating session chooses a role, never a
model.

| Agent | Role | Runtimes |
|---|---|---|
| `execute` | carries out work whose decisions are already made | Claude Code, OpenCode |
| `verify` | judges whether something is actually true | Claude Code, OpenCode |
| `reviewer` | runs a lifecycle gate: brief, plan, milestone, final | Claude Code, OpenCode |
| `build`, `orchestrator` | lead the work and delegate to the roles | OpenCode |
| `plan` | plans read-only | OpenCode |

## What an agent is made of

| File | What it holds |
|---|---|
| `agents/<runtime>--<name>.md` | one stub per agent: its frontmatter, which names no model, and for a lead, its own text |
| `execute.md`, `verify.md`, `review.md` | each role's text, written once for both runtimes |
| `common.md` | the non-negotiable rules every role shares |
| `block-proportional-execution.md`, `block-report-budget.md`, `block-delivery-contract.md` | the three shared blocks |
| `worker-report.md` | the report format every role returns |
| `agents.json` | each agent's runtime, rendering path, role, and the blocks it carries |
| `requirements.json` | what each role needs, per runtime: its rule, the index it is ranked on and its floor, each budget's price ceiling, and what every candidate must meet |
| `models.json` | the model each role runs, per runtime and budget, with the scores, prices and dates it was chosen on; written by the refresh, never by hand |
| `retired.txt` | files the kit once installed and has retired; no other live file may name them |
| `plan.md`, `orchestrate.md` | the planning and leading roles, written but not composed: the OpenCode leads keep their own text |
| `reread-checklist.md` | the re-read guard's checklist, installed by `--features reread` |

A role agent's file is its stub, then its role text, then what every role
shares. A lead's file is its stub, which carries its own text. Each agent is
rendered once per budget, into `<runtime>/agents/<budget>/<name>.md`, and the
renderings differ only in the `model:` line, which comes from `models.json`.

## How a model is chosen

No stub names a model. `shared/scripts/resolve-models.py` is the refresh: it
reads OpenRouter's catalogue and benchmarks, applies `requirements.json` to
them, and prints, for every agent and budget, the model it runs now, the model
the rules choose, and both prices. With `--apply` it writes `models.json`; then
`build-agents.py` renders the agents from it. The benchmarks need an OpenRouter
key, read from `OPENROUTER_API_KEY` only. The refresh never runs at install or
at delegation: an install places the rendering for the machine's budget, read
from `~/.config/mrcall-ai-kit/budget` (medium when absent), and every budget's
rendering in `~/.config/mrcall-ai-kit/agents/`.

## How each runtime receives the shared parts

**Claude Code has a real include.** `skills:` preloads a skill's full body into
a subagent at startup, so each role names `kit-role-rules` — the rules, the
blocks and the report format — and its file ends at its role text. A personal skill in
`~/.claude/skills/` wins over a project skill of the same name, so a changed
skill can be tried in a project only under another name.

**OpenCode has none**, so its role agents carry the same parts inline. A
markdown agent there has no `prompt:` field — the body is always the prompt —
and `{file:}` belongs to `opencode.json`, passing through a markdown body as
literal text in the inspected OpenCode 1.17.18. The documented frontmatter
fields are `description`, `mode`, `model`, `temperature` and `permission`;
`tools:` is honoured too, so treat that list as documented rather than
exhaustive.

**Codex receives nothing from here** — the kit ships no Codex agent definitions.
