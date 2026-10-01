# Changelog

Versions are `MAJOR.MINOR.PATCH` with the major equal to the harness protocol
(`HARNESS_VERSION` in `shared/scripts/doc-check.py`); the rule and the release
command are in [`docs/documentation-harness.md`](docs/documentation-harness.md),
section "Releasing". Each released section below is the body of its GitHub
Release, after an optional first line naming the commit.

## Unreleased

## v8.2.0 — 2026-10-01

- `shared/scripts/release.sh`: the one way to cut a release. It runs every
  precondition (version shape and major, tag absence, changelog section,
  clean tracked tree, `main` at the remote, gate, shell and Python suites),
  reports each as `PASS` or `FAIL`, and only then tags, pushes and publishes.
  `--dry-run` prints the commands instead of running them.
- `tests/test_codex_roles_install.sh` passes `all` to `ai-help.sh`, so it
  asserts the Codex rows from whichever runtime runs the suite.
- `doc-end` Phase 5: the session that ends the work cuts the release when the
  profile names a `release` command and `Unreleased` is not empty. The gate
  accepts the optional `release` profile key.

## v8.1.0 — 2026-09-29

Commit de232a0. Formerly tagged `v0.2.0`.

## Added

- Native Codex custom `reviewer`, `verify`, `execute`, and `plan` agents, generated from the shared role definitions and installed as loadable TOML profiles.
- A Codex global instruction block that routes reviewed delivery through those agents in repositories using the documentation harness.
- The shipped six-rule `sc` re-read checklist in every generated Claude Code, OpenCode, and Codex agent profile. Existing report formats and reviewer verdict placement remain authoritative.

## Improved

- Codex installation protects operator-owned profiles and edits across `skip`, `backup`, repeat install, and uninstall flows.
- `/ai-help` lists installed Codex agents; `/ai-budget` explains that Codex agents inherit the session model.
- Model resolution excludes Codex's inherited-model profiles from Claude Code and OpenCode budget selection.
- Documentation and delivery checks reflect the measured runtime behavior.

## Verification

The shell and Python test suites, generator check, documentation gate, and real Codex/OpenCode agent probes passed. Claude Code agent runtime behavior remains unverified because the client hit its weekly HTTP 429 usage limit; its generated and installed instructions were checked.


## v8.0.0 — 2026-09-28

Commit 657d506. Formerly tagged `v0.1.0`.

First tagged release of MrCall AI-Kit, a reusable configuration for Claude Code, Codex, and OpenCode.

## Included

- Documentation workflows (`doc-create`, `doc-start`, `doc-end`) with a mechanical repository gate and reviewed delivery roles.
- Shared agent roles with budget-based model selection, plus Claude Code routing and OpenCode orchestration.
- An opt-in re-read feature: `/sc` on Claude Code and OpenCode, `$sc` on Codex. Claude Code uses a Stop hook for eligible answers. OpenCode and Codex ask the answering model to apply the installed checklist in the current turn.
- Installer, uninstaller, help, tutorial, and documentation-check repairs for the shipped workflows.

## Verification and limits

The release commit passed 15 shell test scripts, 47 repository Python tests, 87 shared-script Python tests, the generated-agent check, and the documentation gate. OpenCode and Codex re-read entry points were exercised in isolated real clients; the operator also reported that `$sc` works in their installed Codex session. Claude Code's existing Stop hook passed its local checks, but this port did not receive a repeat live Claude Code test.

OpenCode and Codex have no pre-delivery interception or always-on re-read mode. Claude Code skips the re-read pass for answers shorter than 500 characters by default. See `docs/reread-guard.md` for the runtime evidence and boundaries.

