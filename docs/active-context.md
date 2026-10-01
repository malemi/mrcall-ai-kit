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
rule in the repository's `.claude/settings.json`.

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
- Whether a Codex or OpenCode session can push and call `gh` from inside its
  sandbox when `doc-end` cuts a release is unverified.

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
