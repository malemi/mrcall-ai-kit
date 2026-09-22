# Where an agent's rules are written

The agent layer was 23 definitions and 2281 lines, of which 836 — 37% — were
three blocks copied into nineteen worker files. This directory holds those
blocks once. `shared/scripts/build-agents.py` composes every shipped agent file
from a per-agent stub plus the blocks that agent already carried, and
`tests/test_agents_generated.sh` fails when a shipped file and its sources
disagree.

## What is wired today

| File | Role |
|---|---|
| `block-proportional-execution.md`, `block-report-budget.md`, `block-delivery-contract.md` | the three shared blocks, written once |
| `agents/<runtime>--<name>.md` | one stub per agent: its frontmatter, and its own text — whatever this agent says that no other agent says |
| `agents.json` | which blocks each agent carries, taken from what it already had |

A stub is the truth about one agent. A block is the truth shared by many. The
generator joins them; nothing else writes an agent file.

**Regenerating changes no agent's contract.** Which blocks an agent gets is
recorded from what that agent already had, so this was a deduplication and not
a rewrite: zero lines were lost against the previous files, checked line by line.

## How each runtime receives the blocks

**Claude Code has a real include.** `skills:` preloads a skill's full body into
a subagent at startup, so its agents name `kit-role-rules` and end at their own
text. Verified end-to-end rather than assumed: a worker whose body no longer
contains a rule quoted it verbatim, with zero tool calls.

**OpenCode has none**, so its agents carry the blocks inline. A markdown agent
there has no `prompt:` field — the body is always the prompt — and `{file:}`
belongs to `opencode.json`, passing through a markdown body as literal text.
Both established by probe on 1.17.18 with `opencode debug agent`, which resolves
an agent without calling a model. The documented frontmatter fields are
`description`, `mode`, `model`, `temperature` and `permission`; `tools:` is
honoured too, so treat that list as documented rather than exhaustive.

**Codex receives nothing from here** — the kit ships no Codex agent definitions.

## What is NOT wired: the role taxonomy

`common.md`, `worker-report.md`, `execute.md`, `verify.md`, `review.md`,
`plan.md` and `orchestrate.md` describe a target that is **not adopted**: five
roles replacing 23 model-named agents, with the model becoming a frontmatter
field rather than an identity. Nothing generates from them today.

They are kept because the analysis behind them holds — 17 of the 23 agents do
one job, and the rules that matter most were in three files and absent from
sixteen — but adopting them renames files that `install.sh`, `llms.md`, two test
scripts and a permission pattern in `build.md` all refer to by name. That rename
is a separate change, and it is now cheap, because every agent file is generated
from one place.

Until then: **edit a stub or a block, then regenerate.** Never edit a shipped
agent file; the gate will catch you, which is the point.
