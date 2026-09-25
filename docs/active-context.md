---
doc_baseline_commit: d84a4107e9a25ef5eca1755e5199cad0dfb3b51b
doc_baseline_date: 2026-09-09
---

# Active Context

<!-- doc-scope:start -->
Scope: Volatile snapshot of current verified state, unresolved work, and immediate next actions; never session history or durable design.
<!-- doc-scope:end -->

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Documentation harness v8 makes root `CLAUDE.md` a managed template below 200
lines that imports project-owned `AGENTS.md`. It retains the autonomous
engineering-lead contract and adds two delivery lanes: a strict direct fast path
for local, obvious, reversible work with one focused real check, and independent
brief, plan, milestone, and final review gates for all substantial development.
Repository instructions, orientation, and the thin-index budget remain entirely
in `AGENTS.md`.

OpenCode's orchestrator, build lead, read-only planner, reviewer, command, and
orchestrator skill carry the same lifecycle. Build and plan may invoke the
reviewer; plan reviews brief text before drafting plan text and never writes or
implements. The `reviewer` role judges all four artifact kinds read-only, on
Claude Code and on OpenCode.
Direct implementation, positive-value delegation, bounded fan-out, and
proportionate verification remain intact.

Standing instructions are pulled, not pushed. The router hook prints only this
session's shared-memory path and the protocol for using that file, and prints
nothing at all when no `docs/` tree is in reach; the contract itself reaches a
session through the managed `CLAUDE.md` and each role agent's `description`.
Two installed shortcuts pull an instruction on demand: `nr` answers one question
with no tool, subagent, work trace or review gate, refusing to guess and
refusing an action request, and `av` restates the engineering-lead stance. Both are typed commands on Claude Code and
OpenCode and model-invoked skills on Codex, which has no operator-typed prompt
directory. Claude Code also offers its typed commands to the model itself, and
OpenCode reads the Codex skills directory, so on a Codex-inclusive install every
runtime can reach them without the operator typing anything. Each description
therefore carries a run-only-when-asked instruction — an instruction, not a
mechanism — and declares `$nr` or `$av` at the head of a message as its trigger,
which on Codex is the only form there is. Both were exercised in all three real
clients, including the refusal paths and the bare no-argument case.

Agents are named for their job, and their models are data. Each role's needs
per runtime are in `shared/roles/requirements.json`. The refresh,
`shared/scripts/resolve-models.py`, run by the maintainer with
`OPENROUTER_API_KEY`, reads OpenRouter's catalogue and benchmarks, prints what
would change, and with `--apply` writes the choice for every runtime, budget and
role to `shared/roles/models.json`; `build-agents.py` renders each agent once
per budget. An install puts every budget's rendering in
`~/.config/mrcall-ai-kit/agents/` and the machine's budget (the `budget` file
there, medium when absent) at the runtime paths. `/ai-budget low|medium|high`
switches between those renderings without the checkout: Claude Code runs the
new models from its next delegation, OpenCode from its next start. The kit's
OpenCode agents run on OpenRouter routes, so an OpenCode without an OpenRouter
provider cannot run them.

`/ai-help` reads the filesystem and shows the runtime it is running in, with
`all` for every runtime installed. Its listing comes from
`shared/scripts/ai-help.sh`, installed beside `doc-check.py` in the kit-global
home: Claude Code delimits an injected shell block with backticks, so a script
that formats a model column cannot live inline in the command. Descriptions are
one line: the cost of that command is the model re-emitting them, not the disk.

Static profile and installation tests cover every shipped entry point, and both
delivery lanes are verified through installed artifacts in a real Claude Code
client: a one-word local correction completes in about ten seconds with no
subagent or work trace, while a public CLI change is held at brief approval
before planning, at plan approval before code, then at separate milestone and
final reviews.

The optional scope guard remains under the
[`scope-guard execution plan`](execution-plans/2026-08-26-scope-guard.md).
Claude Code's current `MessageDisplay` event carries indexed `delta` batches;
the adapter now assembles them through `final` before attesting. A real
main-session `Edit` in non-interactive mode verified one denial, a visible nonce
reason, and one successful retry. Other runtime and Claude interaction modes
remain unverified.

## Unresolved

- Scope-guard capability levels beyond Claude Code's main-session `-p` `Edit`,
  including interactive mode, `Write`, resume, subagents, and other runtimes,
  still require real-client verification.
- A routed session can still skip creation of its instructed session-memory
  file; the injected note is not deterministic enforcement.
- Nothing prevents a model from invoking `nr` on its own judgement and thereby
  suspending its own tools and checks, wherever the model-invocable form is
  installed. The guard is the description's run-only-when-asked instruction.
- OpenCode's orchestration behavior has install-level but no real-client proof;
  the shortcuts are verified there, the orchestrator agents are not.
- The shell's `ANTHROPIC_API_KEY` takes precedence over the working Claude
  subscription login and leaves non-interactive requests at zero API tokens;
  removing that variable for the process restores normal client execution.
- `install.sh` installs `claude/commands/scope-guard.md` to one destination
  twice when the router and scope-guard features are selected together; see
  [`harness-backlog.md`](harness-backlog.md).
- Codex has no kit-installed global primary profile. Its doc workflows load the
  managed harness contract explicitly, while general sessions remain governed
  by Codex's user-owned global and project `AGENTS.md` chain.

- On Claude Code, `execute` runs `claude-sonnet-5` at low and medium, marked
  below its coding floor of 73, until a Claude model priced at or under the
  ceiling scores 73 or more.
- A scored model priced at $0 that is not a `:free` variant passes the
  resolver's filter, and `execute` would take it at every budget. None is
  scored today.
- The public catalogue carries the same Artificial Analysis scores as the keyed
  benchmarks endpoint (190 of 190 agreed on 2026-09-25), so a refresh could run
  without a key. The refresh reads the keyed endpoint.
- Whether a resolved model does its role's job well is not measured, and other
  machines' installs and OpenCode providers are not checked.

## Next

- Refresh the models when prices or scores move: run
  `shared/scripts/resolve-models.py` with `OPENROUTER_API_KEY`, read the diff,
  then `--apply`, `build-agents.py`, the gate, and a commit.

- Remove the stale Claude API-key configuration at its owning shell-config
  source, so non-interactive client runs stop needing the variable cleared for
  the process.
- Complete the remaining scope-guard implementation plan, then run the installed
  clients through the same activation and write flows operators use.
- Record measured capability levels and limitations in
  [`scope-guard.md`](scope-guard.md) without promoting unit-test results to
  runtime proof.
