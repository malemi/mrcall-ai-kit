# Changelog

Versions are `MAJOR.MINOR.PATCH` with the major equal to the harness protocol
(`HARNESS_VERSION` in `shared/scripts/doc-check.py`); the rule and the release
command are in [`docs/documentation-harness.md`](docs/documentation-harness.md),
section "Releasing". Each released section below is the body of its GitHub
Release, after an optional first line naming the commit.

## Unreleased

## v9.2.0 — 2026-10-08

- Customized CLAUDE upgrades request concrete preservation/adoption consent
  instead of ending as refused. Explicit hash-bound adoption retains original
  instruction bytes/mode in the transaction and rejects stale authorization.

- Documentation upgrades no longer require native compatibility reports or an
  escape flag. Supplied reports remain strictly validated; ordinary upgrades
  record compatibility as not evaluated. The workflow resolves routine local
  documentation defects within upgrade scope. Staging references application
  and child-repository trees instead of copying their contents.

- Verification: seven focused CLI scenarios passed on the installed helper
  and release checkout, including exact rollback and consent boundaries. Native
  client compatibility and broad regression suites are explicitly deferred.

## v9.1.0 — 2026-10-07

- Migration supports explicit operator deferral through `--allow-unverified`,
  retaining ownership checks, staged mechanical validation and exact rollback.
  Codex 0.160.1 and OpenCode 1.18.34 version identities are accepted; fresh
  native compatibility verification remains pending.
- Added the bounded OpenCode compatibility collector/report CLI and explicit
  stop instructions for downstream agents encountering missing prerequisites.
- Release accepts explicit `--skip-tests` for operator-authorized test deferral;
  other release checks remain enforced. This release defers regression and
  native testing at the operator's request.

- The kit repository now mechanically enforces the protocol/release
  invariant: the gate refuses `main` — and every branch of the checkout the
  installed `doc-check.py` resolves into — when `HARNESS_VERSION` differs
  from the newest release tag's major, downgrading to an advisory while a
  release is in flight (a `## vN.x.y` changelog section with no tag yet).
  `doc-end` Phase 5 gains the matching lifecycle: a fast-forward-only merge
  entry for protocol releases, a retry exit for a retained untagged version
  section, and a major-release recovery that keeps the section as the
  pending-release marker.
- The `plan` (architect) and `reviewer` role prompts now treat truncation as
  evidence loss: read artifacts whole, scan tool results for truncation
  markers (`truncat`, `[:int]`, `[... N more lines]`, capped-output notices)
  and fetch the remainder, and use partial content only with the operator's
  explicit approval. Regenerated the Claude Code, Codex, and OpenCode agents.

## v9.0.0 — 2026-10-06

- Harness v9 consolidates repository delivery instructions into one managed
  AGENTS.md block. Explicit migration preserves project content, verifies
  compatibility evidence, recognizes exact legacy templates, and supports
  rollback; customized CLAUDE files stop migration.
- Ordinary requests now select documentation entry and closure by task scope.
  Compact startup output preserves findings without loading unrelated histories;
  read-only and artifact-only requests stay limited.
- Completion checks bind real commands and review references to task/worktree
  content, reject stale evidence, recover pending obligations, and finalize only
  reviewed baseline/status metadata. Task locks prevent concurrent lost updates.
  These checks do not force a host to invoke them or authenticate model judgment.
- Installed workflows, generated roles, and copy/symlink ownership checks use
  the v9 contract. Release requires explicit task authorization. Runtime support,
  measured startup costs, and bypasses are recorded separately from source tests.

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
