# Active Context Archive

Pruned session narrative from [`active-context.md`](active-context.md), dated,
newest first, preserved verbatim. Cold storage: never read by `/doc-start`,
queried on demand to answer "when did we do X" without reconstructing it from
`git log -p`.

## 2026-10-05 — Replaced v8 operational snapshot

````markdown
---
doc_baseline_commit: e08c5fbb1af71baef41aa2d0379a194fc86f1e72
doc_baseline_date: 2026-10-01
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

Every generated kit agent on Claude Code, OpenCode, and Codex now carries the
six shipped `sc` rules and an instruction to check its final report privately.
Claude roles receive them through `kit-role-rules`; OpenCode roles and leads
carry them inline; Codex roles carry them in `developer_instructions`. Fixed
report headers and reviewer verdict position take precedence over answer-first
wording. The private re-read is not observable. Claude Code's `execute`,
`verify` and `reviewer` agents run as installed and return the kit's report
format.

Claude Code and OpenCode use the kit's resolved role models at the selected
`/ai-budget` level. Their renderings are stored under
`~/.config/mrcall-ai-kit/agents/`; OpenCode also needs an OpenRouter provider.
Codex has four installed custom agents — `execute`, `plan`, `reviewer`, and
`verify` — with physical TOML profiles under `~/.codex/agents/`. They inherit
the session model. The global Codex `AGENTS.md` block instructs leads to use
these agents for reviewed delivery; it does not mechanically enforce reviews.

`/ai-help` reports the installed runtime inventory from the filesystem through
`shared/scripts/ai-help.sh`.

The kit is versioned `MAJOR.MINOR.PATCH` with the major equal to
`HARNESS_VERSION`; tags `v8.0.0` and `v8.1.0` and their GitHub Releases are
live. `CHANGELOG.md` holds the notes per version. The session that ends the
work cuts the release: `doc-end` Phase 5 reads `release =
shared/scripts/release.sh` from `docs/.doc-profile`, chooses the version from
`Unreleased`, commits, pushes and runs the script, which refuses on nine
preconditions and reports each as `PASS`/`FAIL`. `tests/test_release.sh`
proves the refusals and the release path against a bare remote and a `gh`
stub. A Claude Code session in auto mode runs the script through the allow
rule in the repository's `.claude/settings.json`; headless Codex
(`codex exec`, full-access sandbox) and OpenCode (`opencode run`) reach the
remote, hold the `gh` login and run the script's full check set.

## Unresolved

- Scope-guard capability levels beyond Claude Code's main-session `-p` `Edit`,
  including interactive mode, `Write`, resume, subagents, and other runtimes,
  still require real-client verification.
- A routed session can still skip creation of its instructed session-memory
  file; the injected note is not deterministic enforcement.
- Nothing prevents a model from invoking `nr` on its own judgement and thereby
  suspending its own tools and checks, wherever the model-invocable form is
  installed. The guard is the description's run-only-when-asked instruction.
- OpenCode's `orchestrator` agent still has no real-client proof.
- The shell's `ANTHROPIC_API_KEY` takes precedence over the working Claude
  subscription login and leaves non-interactive requests at zero API tokens;
  removing that variable for the process restores normal client execution.
- The Codex global block and custom profiles are instructions, not mechanical
  enforcement that every substantial session performs each review gate.
- On Claude Code, `execute` runs `claude-sonnet-5` at low and medium, marked
  below its coding floor of 73, until a Claude model priced at or under the
  ceiling scores 73 or more.
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
````

## 2026-09-29 — Agent and re-read runtime evidence

The re-read feature's OpenCode `/sc` and Codex `$sc` paths passed isolated
real-client checks. The operator also reports that `$sc` works in the current
Codex client after installation. Both paths are instruction-based; the existing
Claude Code `/sc` uses a Stop hook. The operator waived repeat Claude client QA for this port.
See the [runtime support matrix](reread-guard.md) for proof and limits.

An OpenCode 1.18.32 `build` session delegated to the installed `reviewer` in a
disposable directory, and the child put the correct `No` verdict in its first
report field. A Codex 0.158.0 spawned reviewer also preserved its verdict
field while finding a brief overclaim. Claude Code 2.1.280 returned its weekly
usage limit before the agent ran; its installed skill and agents match the
generated files, with no new runtime-behavior proof for this change.

Codex has four installed custom agents: `execute`, `plan`, `reviewer`, and
`verify`. Their TOML definitions are generated from the shared role text and
copied to `~/.codex/agents/` even in symlink install mode: Codex 0.158.0
rejected symlinked roles, and a fresh CLI session accepted the copied
`reviewer`. A delimited global `~/.codex/AGENTS.md` block tells a lead in a
bootstrapped repository to load `CLAUDE.md` and use the named reviewer. A fresh
CLI session received that block without file reads and returned the reviewer's
`REVISE` verdict in the kit report format. Codex roles inherit the session
model; `/ai-budget` reports that it does not switch them.

The public catalogue carries the same Artificial Analysis scores as the keyed
benchmarks endpoint (190 of 190 agreed on 2026-09-25), so a refresh could run
without a key. The refresh reads the keyed endpoint.

## 2026-09-29 — Details removed from the living snapshot

OpenCode and Claude Code use the same reviewed delivery lifecycle described in
[`documentation-harness.md`](documentation-harness.md).

Standing instructions are pulled, not pushed. The router hook prints only this
session's shared-memory path and the protocol for using that file, and prints
nothing at all when no `docs/` tree is in reach; the contract itself reaches a
session through the managed `CLAUDE.md` and each role agent's `description`.
The `nr` and `av` shortcuts remain on-demand instructions: typed commands on
Claude Code and OpenCode, model-invoked skills on Codex. Their Codex trigger
descriptions are instructions, not enforced dispatch rules.

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

## 2026-09-28 — Reviewed delivery, shortcuts, and re-read port

OpenCode's orchestrator, build lead, read-only planner, reviewer, command, and
orchestrator skill carry the same lifecycle. Build and plan may invoke the
reviewer; plan reviews brief text before drafting plan text and never writes or
implements. The `reviewer` role judges all four artifact kinds read-only, on
Claude Code and on OpenCode.
Direct implementation, positive-value delegation, bounded fan-out, and
proportionate verification remain intact.

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

The re-read feature extends Claude Code's existing `/sc` to OpenCode and Codex.
The `2026-09-27-reread-guard-cross-runtime` plan is completed. OpenCode's typed
`/sc` inserts the installed procedure and checklist into its prompt; Codex's
`$sc` skill reads them in-turn. Isolated real-client checks on OpenCode 1.18.32
and Codex CLI 0.157.1 observed checklist use on short and long answers, missing
file errors, and the one-shot command boundaries. Both paths are instruction
based. Claude's existing Stop-hook test passes. Live Claude Code 2.1.280 could
not run `/sc` because the client reported a weekly usage limit. The operator
said the existing command worked before this port and waived a repeat live
check; this trace establishes no new Claude client behavior. Independent
milestone and final integration reviews approved the port.

`/ai-help` reads the filesystem and shows the runtime it is running in, with
`all` for every runtime installed. Its listing comes from
`shared/scripts/ai-help.sh`, installed beside `doc-check.py` in the kit-global
home: Claude Code delimits an injected shell block with backticks, so a script
that formats a model column cannot live inline in the command. Descriptions are
one line: the cost of that command is the model re-emitting them, not the disk.

## 2026-08-25 — the router's pre-live verification record

Superseded by live use on 2026-08-25, when the router drove a full working
session. Kept because it is the record of what had and had not been proved
before that.

`/router`'s `on`/`off`/`status`/`unregister` output was rewritten (commit
`4918e1a`): it had been printing internals (flag file, symlink, settings.json
registration) on every call; it now prints state plus the next command only,
and expands only when something is actually broken (flag set but hook not
registered).

Mechanically verified: 45 `doc-check.py` pytest cases and
`tests/test_router_install.sh` (8 assertions — sandbox install alone, dropped
without Claude Code selected, no duplicate `worker-fable` manifest entry when
combined with doc-harness, uninstall removes exactly the router artifacts, hook
dormancy/injection, the session path held across a cd, an existing session file
adopted rather than duplicated, the start directory recovered from the
transcript path) all pass; the mechanical gate is clean on this repo. **Not yet
verified live** — the router has been switched on for real on this machine
(hook registered in `~/.claude/settings.json`, flag present), but no session has
cleanly exercised actual trivial-vs-delegated routing or the session-memory
write/read/promote cycle end to end.

Every live attempt up to that point had had a more specific override in play:
Plan Mode superseding routing for one task, `doc-end`'s own non-delegable
phases for a consolidation.

## 2026-08-21 — Router feature confirmed committed; status-output UX fix

Earlier `active-context.md` stated the router feature (hook, `/router`
command, session-memory contract, `/ai-help`) was "currently uncommitted in
the working tree," pending a live smoke test before committing. That
sentence became stale: the feature was committed (`19cfc61`) before this
correction was made, without the smoke test having passed — a deliberate
call left open by the prior wording ("or sooner, if the router feature is
committed unverified — that's a call for whoever runs the smoke test to
make explicitly, not a default").

## 2026-08-15 — Harness v3 in force; work-trace rule with four enforcement points (as recorded)

Harness v3 is implemented and committed across Claude Code, Codex, and
OpenCode. The full contract lives in
[`documentation-harness.md`](documentation-harness.md); enforcement of the
living-context shape is three-layered, with the heading half mechanical in
`doc-check.py`. `doc-end` delegates to pinned-model workers (`worker-sonnet`
mechanical, `worker-opus` verification) where the environment provides them;
gathering the session signal and deciding what is current stay non-delegable.
All `doc-*` workflows require an exact `harness_version` match before doing
work.

The work-trace rule is in force (2026-08-14): orchestrated or multi-session
work creates `docs/briefs/YYYY-MM-DD-<slug>.md` +
`docs/execution-plans/YYYY-MM-DD-<slug>.md` before execution, with lifecycle
only in the plan's `status` frontmatter. Four enforcement points: `doc-create`
ships the briefs directory and writes the one-line pointer into the configured
index (the trigger binding — it fires exactly in harness repos); `doc-end`
Phase 3 creates a missing pair in-session and must fill a mandatory *work
trace* output slot; a delegated `doc-critic` reports a `TRACE:` finding
instead of inventing content; `doc-check.py` reports undated trace filenames
as an advisory. The OpenCode orchestrator persists this pair natively (its
private `docs/plans/execution.md` schema is gone) and its question templates
are in English.

The gate emits two advisory families, never affecting the exit code:
`doc_max_lines` (default 400, archive exempt) and undated work-trace
filenames. 36 checker tests pass. The root `README.md` is human-facing (82
lines: value proposition plus two-minute install; protocol internals live
only in the contract). This machine installs the kit in symlink mode, so the
installed commands and checker track the working tree with no reinstall.

## 2026-08-04 — Harness v3: shape enforcement, workers, version handshake (as recorded)

Harness version 3 is implemented across Claude Code, Codex, and OpenCode.
Pruned `active-context.md` narrative now moves to `active-context-archive.md`
(dated, newest first, verbatim, never read by `doc-start`) instead of being
discarded: `doc-end` Phase 3 archives it proactively every session, and
`doc-critic` independently checks the file's shape — the backstop for the exact
failure the plain instruction alone did not prevent (a real downstream repo's
`active-context.md` grew from ~120 to ~1500 lines over two months of sessions
that each said "consolidate"). Whether that check repairs or only reports
follows the delegation boundary: in-session it repairs, delegated it reports a
blocking finding, because sorting current from historical needs the transcript
a subagent does not have. The repair was verified against a real scratch
fixture, byte-for-byte zero information loss.

Since v3 the heading half of that shape is **mechanical**: `doc-check.py`
fails on any `##` section in `active-context.md` outside the canonical three
(code fences excluded; the archive exempt). The two LLM layers above it each
failed in practice — one repo drifted to ~1500 lines over two months of
consolidations, then lost 1436 lines and four durable invariants to a session
that never invoked `doc-end` at all, which no instruction to an agent can
prevent. Replayed against that repo's real pre-trim file, the check reports 27
violations. The durable contract is in
[`documentation-harness.md`](documentation-harness.md); 21 checker tests + the
Codex install layout test pass.

`doc-end` delegates its delegable work to pinned-model workers where the
environment has them: `worker-sonnet` for mechanical execution, `worker-opus`
for independent verification. Claude Code gets them from `claude/agents/`,
installed to `~/.claude/agents/` with `doc-harness`; OpenCode already had
`worker-sonnet` in its own roster. Because each worker declares `model:`, the
tier follows the task rather than the session — verified live in both
directions. Gathering the session signal and deciding what is current are
declared non-delegable: only the session holding the transcript can do either.

All `doc-*` workflows now require an exact `harness_version` match before doing
work. Directional failures distinguish a stale installed kit from repository
docs that need an explicitly authorized migration.

Codex receives native user-level skills under `$HOME/.agents/skills`; install
and uninstall were verified in disposable HOME directories in both copy and
symlink modes.

## 2026-07-25 — OpenRouter Auto Router experiment

The OpenRouter Auto Router experiment is complete. The working OpenCode agent
model ID is `openrouter/openrouter/auto`, and delegation was verified
end-to-end. Retained evidence and superseded hypotheses live in
[`briefs/2026-08-01-test-worker-auto.md`](briefs/2026-08-01-test-worker-auto.md), not in this volatile
snapshot.
