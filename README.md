# MrCall AI-Kit

Project memory, reviewed delivery and persistent supervision for **Claude Code**,
**Codex** and **OpenCode**.

AI-Kit installs reusable commands, skills and agent roles into the coding tools
you already use. Repository documentation carries context between sessions;
review workflows connect changes to evidence; a dedicated supervisor can follow
other sessions and steer unfinished work toward its intended result.

[Get started](#get-started) · [Supervise sessions](#supervise-sessions) ·
[Commands](#commands-and-skills) · [Documentation](docs/README.md) ·
[Release notes](CHANGELOG.md)

## What you get

| Capability | What it does | Available in |
|---|---|---|
| **Project memory** | Start from current repository context; reconcile documentation when work ends. | Claude Code, Codex, OpenCode |
| **Reviewed delivery** | Use briefs, plans, independent reviews and recorded verification for substantial changes. | Claude Code, Codex, OpenCode |
| **Persistent supervision** | Check connected sessions on a real clock, retain failures and decisions, and send concrete next actions to their leads. | Codex, Claude Code¹ |
| **Test pruning** | Remove redundant tests while preserving distinct functional risks and recording the reasons in repository memory. | Claude Code, Codex, OpenCode |
| **Specialized agents** | Delegate execution, causal debugging, verification, planning and review to roles with explicit responsibilities. | Runtime-specific roles on all three clients |
| **Model budgets** | Select a budget for the kit's Claude/OpenCode roles and inspect their configured models. | Claude Code, OpenCode |
| **Orchestration** | Run OpenCode's engineering-lead workflow for substantial implementation. | OpenCode |
| **Session router** | Opt into model routing and a shared session-memory file. | Claude Code |

¹ The Claude supervisor adapter runs on **Linux** with the client's
**peerProtocol 1**; it is measured on Claude Code 2.1.296 and 2.1.323. Codex
evidence covers CLI/app-server 0.164.0 and 0.169.0 on Linux.
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
supervision are selected separately. Run `./install.sh --help` for the complete
feature list, or add `--dry-run` to inspect an installation before applying it.

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

Completion records track which checks and reviews apply to which content.
They can reject missing or stale evidence when invoked; instructions cannot
force a client to run a workflow it skips. See the
[harness contract](docs/documentation-harness.md) and
[measured client behavior](docs/harness-runtime-support.md).

## Supervise sessions

Install supervision for the client that will host the supervisor:

```bash
./install.sh --environment claude --features supervision \
  --mode copy --on-exist backup --yes
```

Use `--environment codex` for Codex, or `all` to install both supported entries.
OpenCode's orchestrator is a separate feature.

In a **dedicated session**, invoke `supervisor` and identify the session and result
you want it to follow. A short request is enough:

> Use supervisor to follow PROBLEMI2 until its task is completed and verified.

The skill resolves exact session identities and shows the effective mandate and
configuration before activation. It supplies its own supervision rules; you do
not need to repeat them in every prompt. Each binding connects sessions of the
same runtime. Workers remain under their lead's control.

The supervisor is instructed to wake an idle lead when authorized work remains,
check actual progress, preserve unexplained failures and distinguish a real
blocker from a long operation. Explicit observation-only mandates stay read-only.

Python and user cron provide the clock. A minute tick checks for due tasks;
assessments default to every ten minutes. There is **no default check-count cap**.
Operator limits remain binding, and health checkpoints do not terminate useful work.
Tasks, memory and delivery history persist across restarts.

Installation is **dormant**: it starts no sessions, enables no cron entry and
makes no model calls. Activation is separate; due assessments can consume model
credit. A delivered message proves receipt, not compliance or completion.
Native transport checks do not establish reliable supervisory judgment.

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
| `supervisor` | Supervise connected Codex or Claude sessions; manage tasks, memory and detachment. |
| `test-prune` | Audit and consolidate tests with retained rationale. |
| `nr` | Answer one question immediately, without the repository workflow for that turn. |
| `av` | Restate the engineering-lead stance: decide and finish authorized work. |
| `sc` | Re-read an answer against the installed checklist. |
| `verification-warnings` | Inspect missing or stale check receipts; optionally enable runtime notifications. |
| `scope-guard` | Manage optional protection for marked Markdown documents. |
| `/ai-budget` | Inspect or change Claude/OpenCode role budgets: `low`, `medium`, `high`. |
| `/router` | Manage Claude's opt-in model router and session memory. |
| `/orchestrator` | Use OpenCode's reviewed engineering-lead workflow. |
| `/migrate-check` | Assess a move from Claude Code to OpenCode. |

`nr` and `av` require an explicit request; they are not always-on modes. Automatic
av is disabled. Doc-harness installation retires its owned automatic registrations
while preserving manual invocation and unrelated hooks.

Claude and OpenCode role models follow `/ai-budget`; **Codex roles inherit the
session model**. Agent names describe their jobs, not a model choice. See the
[role definitions and model-selection rules](shared/roles/README.md).

Ask the lead to use `debugger` when a failure's cause is uncertain. Supply the
actual failing input, entry command, expected behavior and evidence paths.
The role follows the data function by function to the first demonstrated
divergence, separates observations from hypotheses and hands a diagnosis to
`execute`. It does not apply the correction. Install the new role by rerunning
the installer for your selected clients/features, then start a fresh session.
Codex/Claude receive it with `doc-harness`; OpenCode also receives it with
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
files. For supervision, it disables owned cron entries before removing helpers;
task history, memory and the dependency environment remain available.
[Removal details](docs/supervision.md#stop-and-remove).

## Further reading

- [Documentation index](docs/README.md) — durable contracts and current context.
- [Runtime support](docs/harness-runtime-support.md) — measured client behavior.
- [Scope guard](docs/scope-guard.md) and [verification warnings](docs/verification-warnings.md) — optional protections and their limits.
- [Re-read behavior](docs/reread-guard.md) and [automatic-av retirement](docs/runtime-completion.md).
- [Repository layout and operating rules](AGENTS.md) — the project-owned index.
- [Changelog](CHANGELOG.md) — releases and verification boundaries.

## License

MIT — use it, fork it, improve it.
