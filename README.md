# MrCall AI-Kit

Project memory and reviewed delivery for **Claude Code**, **Codex** and
**OpenCode**.

AI-Kit installs reusable commands, skills and agent roles into the coding tools
you already use. Repository documentation carries context between sessions, and
review workflows connect changes to evidence. Its managed instructions tell
agents to decide and finish the work, and to ask you only for a credential, a
payment or a choice you reserved. An experimental supervisor can follow other
sessions; in its native trial it did not move the supervised work forward.

[Get started](#get-started) · [Commands](#commands-and-skills) ·
[Supervise sessions](#supervise-sessions) · [Documentation](docs/README.md) ·
[Release notes](CHANGELOG.md)

## What you get

| Capability | What it does | Available in |
|---|---|---|
| **Project memory** | Start from current repository context; reconcile documentation when work ends. | Claude Code, Codex, OpenCode |
| **Reviewed delivery** | Use briefs, plans, independent reviews and recorded verification for substantial changes. | Claude Code, Codex, OpenCode (its `reviewer` role comes with `orchestration`) |
| **Specialized agents** | Delegate execution, causal debugging, verification, planning and review to roles with explicit responsibilities. | Runtime-specific roles on all three clients |
| **Test pruning** | Remove redundant tests while preserving distinct functional risks and recording the reasons in repository memory. | Claude Code, Codex, OpenCode |
| **Model budgets** | Select a budget for the kit's Claude/OpenCode roles and inspect their configured models. | Claude Code, OpenCode |
| **Orchestration** | Run OpenCode's engineering-lead workflow for substantial implementation. | OpenCode |
| **Session router** | Opt into model routing and a shared session-memory file. | Claude Code |
| **Persistent supervision** (experimental) | Observe connected sessions on a real clock, record decisions and spend, and send next actions to their leads. | Codex, Claude Code¹ |

¹ The Claude supervisor adapter runs on **Linux** with the client's peer
protocol 1; it is measured on Claude Code 2.1.296 for sends and 2.1.323 for the
rest. Codex evidence covers CLI and app-server 0.169.0 on Linux.
See [supervision setup and measured support](docs/supervision.md).

## Get started

```bash
git clone https://github.com/malemi/mrcall-ai-kit.git
cd mrcall-ai-kit
./install.sh
```

The installer detects your tools and asks which features to install. It writes
to your user configuration, never into your project repositories. Choose copy
or symlink installation and how existing files should be handled.

For a noninteractive documentation-harness installation on all three clients:

```bash
./install.sh --environment all --features doc-harness \
  --mode copy --on-exist backup --yes
```

The documentation harness includes `test-prune`. Optional features such as
shortcuts, the router or supervision are selected separately. Run
`./install.sh --help` for the complete feature list, or add `--dry-run` to
inspect an installation before applying it.

Then open a fresh coding session in your project and invoke `doc-create`:
`$doc-create` in Codex, `/doc-create` in Claude Code or OpenCode. It creates the
repository's `docs/` harness or guides an explicitly requested migration.
Existing customized instructions require a preservation proposal before adoption.

Once configured, repository instructions direct the lead to load context before
investigation and reconcile it before delivering changes. You can also invoke
`doc-start` and `doc-end` explicitly.

## Work with project memory

The documentation harness gives each repository a small current context, durable
documentation and a trace of substantial work. Its v9 instruction entry is
`AGENTS.md`; it does not require a repository `CLAUDE.md`.

- **Start:** `doc-start` reads the project context and checks documentation integrity,
  baseline drift, working-tree state and open plans.
- **Deliver:** substantial work proceeds through a brief, plan, reviewed milestones
  and a separate final review. Simple questions and small changes keep a smaller scope.
- **Close:** `doc-end` reconciles current knowledge, checks affected claims with
  `doc-critic`, verifies evidence and updates the documentation baseline.

Reviews are internal gates, not approval prompts. The managed instructions tell
the lead to decide from evidence and to ask the operator only for what only the
operator holds: a credential, a payment, or a choice the operator explicitly
reserved. A review returns `BLOCKED` only for such an item.

Completion records track which checks and reviews apply to which content.
They can reject missing or stale evidence when invoked; instructions cannot
force a client to run a workflow it skips. See the
[harness contract](docs/documentation-harness.md) and
[measured client behavior](docs/harness-runtime-support.md).

## Supervise sessions

Supervision is experimental. In the kit's own native trial on a Claude Code
lead, the supervision used about a tenth of the measured tokens. It recorded
decisions and summarized state, but it neither reduced the lead's spend nor
found the lead's errors on its own, and the trial was stopped. Deterministic suites test
what Python enforces; whether the supervisor model judges well is not
established.

Install supervision for the client that will host the supervisor:

```bash
./install.sh --environment claude --features supervision \
  --mode copy --on-exist backup --yes
```

Use `--environment codex` for Codex, or `all` to install both supported entries.
OpenCode's orchestrator is a separate feature.

In a **dedicated session**, invoke `supervisor` and name the sessions and the
result you want. A short request is enough:

```text
Use supervisor to follow the session api-fix until its task is completed and verified.
```

The skill builds the task from your own messages. Before it creates the task, it
shows the authority text exactly as Python renders it, the operator session and
the session identities. A completion task needs a spend limit; an
operator-written `supervision.json` in the kit home can hold a default. Each
binding connects sessions of the same runtime, and workers remain under their
lead's control.

User cron runs a tick every minute, and Python reads the sessions without a
model call. It keeps the clock, measures spend from the sessions' own token
counters and records every message the kit sends in one ledger. It calls the
supervisor model only when an observation needs judgment, such as a turn
ending, a session starting to wait, an operator message or a spend threshold.
For each target that owns an open acceptance item and is not working, an
assessment ends in an intervention, a wait, a park whose question reaches your
session once, or the task's conclusion. The task interval is the minimum
spacing between assessments, and there is no default cap on their number. A
deadline, an assessment count or a spend ceiling parks an active task; at a
completion task's spend ceiling Python also interrupts the targets' running
turns. A parked task has no ceiling: the park stops the assessments, not the
lead. An observation task never receives an intervention. Tasks, memory, the
ledger and delivery history persist across restarts.

Installation is **dormant**: it starts no sessions, enables no cron entry and
makes no model calls. Activation is separate, and assessments consume model
credit. A delivered message proves receipt, not compliance or completion.

For Python-owned continuation, Codex on Linux supports
[persistent goals](docs/supervision.md#persistent-goals). The controller runs under
your existing account, wakes unfinished idle sessions and closes only after a bound
executable check passes, an operator stop or an explicit limit. Setup requires no
sudo or session migration; installation remains dormant until activation.

[Setup, permissions, recovery and limits →](docs/supervision.md)

## Keep tests useful

Invoke `test-prune` for a test-cleanup task, for example in Codex:

```text
$test-prune tests/
```

The skill audits what each test protects before removing or consolidating it.
It preserves distinct functional risks, records deliberately lost checks and
retains failure evidence and temporary artifacts. With a documentation harness,
its decisions belong under `docs/test-audits/` so the next session can reuse them.
It is not a shortcut for making a failing suite green.

[Workflow](shared/skills/test-prune/SKILL.md) ·
[Repository memory contract](docs/documentation-harness.md#test-pruning-memory)

## Commands and skills

Use `/name` for installed commands in Claude Code and OpenCode. In Codex, invoke
skills with `$name` or ask for them by name. Availability depends on the features
you selected; `/ai-help` and `/ai-tutorial` list installed capabilities in
Claude Code and OpenCode.

| Name | Use it for |
|---|---|
| `doc-create` | Create or explicitly migrate a repository's documentation harness. |
| `doc-start` / `doc-end` | Load current context / reconcile and verify it. |
| `doc-critic` | Check documentation claims against actual code and evidence. |
| `test-prune` | Audit and consolidate tests with retained rationale. |
| `nr` | Answer one question immediately, without the repository workflow for that turn. |
| `av` | Restate the engineering-lead stance and resume the session's open work; only what the operator alone holds, or damage that cannot be undone, goes back to the operator. |
| `sc` | Re-read an answer against the installed checklist. |
| `verification-warnings` | Inspect missing or stale check receipts; optionally enable runtime notifications. |
| `scope-guard` | Manage optional protection for marked Markdown documents. |
| `supervisor` | Supervise connected Codex or Claude sessions (experimental); manage tasks, memory and detachment. |
| `/ai-budget` | Inspect or change Claude/OpenCode role budgets: `low`, `medium`, `high`. |
| `/router` | Manage Claude's opt-in model router and session memory. |
| `/orchestrator` | Use OpenCode's reviewed engineering-lead workflow. |
| `/migrate-check` | Assess a move from Claude Code to OpenCode. |

`nr` and `av` come with the `shortcuts` feature and run only on an explicit
request; they are not always-on modes. Automatic av is disabled. Doc-harness
installation retires its owned automatic registrations while preserving manual
invocation and unrelated hooks.

A process that keeps no session memory, such as a scheduled headless run, sets
`MRCALL_KIT_SESSION_MEMORY=off` in its environment; the router hook then adds
nothing to its turns.

Claude and OpenCode role models follow `/ai-budget`; **Codex roles inherit the
session model**. Agent names describe their jobs, not a model choice. See the
[role definitions and model-selection rules](shared/roles/README.md).

Ask the lead to use `debugger` when a failure's cause is uncertain. Supply the
actual failing input, entry command, expected behavior and evidence paths.
The role follows the data function by function to the first demonstrated
divergence, separates observations from hypotheses and hands a diagnosis to
`execute`. It does not apply the correction. Every client receives it with
`doc-harness`; Claude Code also receives it with `router`, and OpenCode with
`workers`. Runtime shell access is not a guarantee of side-effect-free diagnosis.

## Update or uninstall

Pull the kit's updates, then rerun the installer for the clients and features
you use. Copy installations need an explicit refresh. Symlinks expose source
changes immediately but do not install newly added files. Start fresh sessions
to load newly installed instructions and skills.

```bash
./uninstall.sh --dry-run
./uninstall.sh --yes
```

The uninstaller uses its ownership manifest and preserves foreign or modified
files. For supervision, it removes its own cron entries before the helpers and
keeps foreign cron entries, state roots, the message ledger and the dependency
environment. [Removal details](docs/supervision.md#stop-and-remove).

## Further reading

- [Documentation index](docs/README.md) — durable contracts and current context.
- [Runtime support](docs/harness-runtime-support.md) — measured client behavior.
- [Persistent supervision](docs/supervision.md) — what Python enforces, what a model judges, and measured support.
- [Model router](docs/model-router.md) — session memory, rotation and worker reports.
- [Scope guard](docs/scope-guard.md) and [verification warnings](docs/verification-warnings.md) — optional protections and their limits.
- [Re-read behavior](docs/reread-guard.md) and [automatic-av retirement](docs/runtime-completion.md).
- [Repository layout and operating rules](AGENTS.md) — the project-owned index.
- [Changelog](CHANGELOG.md) — releases and verification boundaries.

## License

MIT — use it, fork it, improve it.
