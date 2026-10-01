---
status: completed
brief: docs/briefs/2026-10-01-release-versioning.md
---

# Execution plan — release versioning tied to the harness protocol

Brief: [`2026-10-01-release-versioning.md`](../briefs/2026-10-01-release-versioning.md),
approved at its gate on 2026-10-01 after one revision.

## Milestones

### M1 — Changelog and the written rule

- Create root `CHANGELOG.md`: intro line stating the versioning rule in one
  sentence and pointing at the harness doc; sections `## Unreleased`,
  `## v8.1.0 — 2026-09-29` (commit de232a0, formerly tagged `v0.2.0`) and
  `## v8.0.0 — 2026-09-28` (commit 657d506, formerly tagged `v0.1.0`). Each
  released section opens with one line naming the commit and the former tag,
  followed by the former release body verbatim. `Unreleased` lists the release
  tooling and the Codex roles test fix.
- Add `## Releasing` to `docs/documentation-harness.md` after the
  compatibility handshake: major = `HARNESS_VERSION`, minor, patch, the
  changelog as the notes source, `shared/scripts/release.sh` as the only
  release path, the refusal list, and that a minor needs `git pull` plus a
  re-run of `./install.sh`.
- Point to `CHANGELOG.md` and `shared/scripts/release.sh` from the `AGENTS.md`
  layout list.
- Verify: gate (`python3 shared/scripts/doc-check.py --repo .`) exits 0;
  `grep -c '^## v' CHANGELOG.md` prints 2.

### M2 — The release script and its test

- `shared/scripts/release.sh vX.Y.Z [--dry-run]`, bash, `set -uo pipefail`,
  run from the checkout root, never installed. It runs **every** check and
  prints one `PASS`/`FAIL` line per check, so one run shows everything that
  is wrong, then exits 1 if any failed. Checks: semver shape; major equals
  `HARNESS_VERSION` read from `shared/scripts/doc-check.py`; no local or
  remote tag of that name (`git fetch --tags` first); `CHANGELOG.md` has a
  `## vX.Y.Z` section with a non-empty body; no modified tracked files
  (`git status --porcelain --untracked-files=no` empty); current branch
  `main` and `HEAD` equal to `origin/main` after `git fetch`; gate exit 0;
  every `tests/test_*.sh` exits 0; `python3 -m pytest -q tests
  shared/scripts/tests` exits 0. All green: annotated tag with message
  `mrcall-ai-kit vX.Y.Z`, `git push origin vX.Y.Z`, `gh release create
  vX.Y.Z --title "mrcall-ai-kit vX.Y.Z" --notes-file <section body>`.
  `--dry-run` runs the same checks and prints the three commands instead of
  running them. `RELEASE_REMOTE` (default `origin`), `RELEASE_BRANCH`
  (default `main`) and `GH_REPO` exist only so the test can point the script
  at a throwaway remote.
- `tests/test_release.sh`: builds a temp checkout with a bare remote, a
  stubbed `gh` first on `PATH` that records its arguments, a git identity set
  through `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, a minimal `doc-check.py` whose
  behavior the test controls (`HARNESS_VERSION = 8`, exit 0 or 1), a
  `tests/test_ok.sh` that exits 0 and a trivially passing pytest file (pytest
  exits 5 on an empty collection). Asserts a `FAIL` line and exit 1 for: wrong
  major; existing tag; missing changelog section; modified tracked file;
  branch not `main`; HEAD ahead of the remote; gate exiting 1; a
  `tests/test_fail.sh` exiting 1; a failing pytest file. Asserts the success
  path creates the annotated tag on the bare remote with message
  `mrcall-ai-kit v8.1.0` and that the `gh` stub received `release create
  v8.1.0 --title "mrcall-ai-kit v8.1.0"` with the section body as notes.
  Asserts `--dry-run` on the green fixture creates no tag and prints the
  three commands.
- The suite step only makes sense if the suite is deterministic across
  runtimes. `tests/test_codex_roles_install.sh` failed from a Claude Code
  session because it called `ai-help.sh` without `all` (the listing hides
  every runtime but the current one); the test now passes `all`. That fix
  ships in this delivery and is recorded in the changelog's Unreleased section.
- Verify: `bash tests/test_release.sh` passes. On the real checkout before
  commit, `shared/scripts/release.sh v8.2.0 --dry-run` reports `FAIL` for the
  changelog section and for modified tracked files and `PASS` for the rest.

### M3 — Commit and push the delivery

- Run the full suite and the gate at the delivery tree; commit M1 and M2
  (and the test fix) by explicit paths; push `main`.
- Verify: `git status --porcelain --untracked-files=no` empty; `HEAD` equals
  `origin/main`.

### M4 — Renumber the existing tags and releases

- Depends on M3: the former release bodies are then committed in
  `CHANGELOG.md`. The byte-for-byte reference for the recreated releases is
  the pair of files saved before any deletion with `gh release view v0.x
  --json body --jq .body` (scratchpad `notes-v0.1.0.md`, `notes-v0.2.0.md`).
- `git tag -a v8.0.0 657d506 -m "mrcall-ai-kit v8.0.0"`, `git tag -a v8.1.0
  de232a0 -m "mrcall-ai-kit v8.1.0"`, push both.
- `gh release create v8.0.0 --title "mrcall-ai-kit v8.0.0" --notes-file
  notes-v0.1.0.md`; same for `v8.1.0` from `notes-v0.2.0.md`.
- `gh release delete v0.2.0 --yes --cleanup-tag`, same for `v0.1.0`; delete
  the local `v0.*` tags.
- Verify: `git ls-remote --tags origin` shows exactly `v8.0.0`, `v8.1.0`;
  `gh release view vX --json body --jq .body` equals the saved file byte for
  byte; `gh release view vX --json name` equals `mrcall-ai-kit vX`.
- Rollback: the saved bodies and the two commit shas recreate either pair of
  tags and releases.

### M5 — Final end-to-end check

- On `main` at `origin/main`, `shared/scripts/release.sh v8.2.0 --dry-run`:
  expected exactly one `FAIL` (no `## v8.2.0` section in `CHANGELOG.md`) and
  `PASS` for every other check, suite and gate included. That is the
  final-user path on the real repository; the full green path is proven by
  the test's success case. `v8.2.0` is cut by M6.
- Mark this plan `completed`; `docs/active-context.md` is reconciled by
  `doc-end`.

### M6 — The session cuts the release (correction of 2026-10-01)

- `shared/scripts/doc-check.py`: `release` joins the known profile keys and
  the non-empty check beside `build`/`smoke`; a pytest case covers accepted,
  empty and absent `release`.
- `docs/.doc-profile`: `release = shared/scripts/release.sh`.
- `shared/commands/doc-end.md` and its byte copy
  `codex/skills/doc-end/WORKFLOW.md` (`tests/test_codex_install.sh` compares
  them): new "Phase 5 — Release", run after the baseline is written.
  Skips, each reported in the new output slot, evaluated in this order and
  before any edit: `release: not configured` (no `release` key);
  `release: none, Unreleased empty` (no non-whitespace line between
  `## Unreleased` and the next version heading); `release: none, not on
  <branch>` (the release branch is `main` unless the repository's rule says
  otherwise); `release: none, uncommitted work in <paths>` (tracked changes
  that are not this run's consolidation edits). Otherwise: choose the version
  by semver from the `Unreleased` content applied to the newest `## vX.Y.Z`
  heading (patch for fixes and docs, minor for a capability or behavior
  change, major when the repository's rule says the protocol moved; the
  kit's rule is "Releasing" in `docs/documentation-harness.md`); rewrite
  `Unreleased` into `## vX.Y.Z — <date>` with a fresh empty `## Unreleased`
  above it; commit `CHANGELOG.md` alone, move `doc_baseline_commit` onto that
  commit, commit the docs-only consolidation edits by explicit path; push
  both; run the profile string verbatim from the repository root with
  `vX.Y.Z` appended. On refusal the phase may choose another version, push,
  commit its own edits, or repair a test this session broke; it never
  deletes or moves a tag, edits `HARNESS_VERSION`, force-pushes, or commits
  tracked changes it did not make. An unfixable refusal ends as `release:
  not cut — <reason>`: the version section goes back under `Unreleased`,
  that revert is committed alone, the baseline moves onto it in a docs-only
  follow-up commit, both are pushed. Success: `release: vX.Y.Z cut`.
  Never hand a release to the operator.
- `.claude/settings.json` (repository, committed): allow
  `Bash(shared/scripts/release.sh:*)` so a Claude Code session in auto mode
  can run the command; the command must be invoked exactly as the profile
  states.
- `docs/documentation-harness.md`: profile schema lists `release` with the
  same older-checker caveat as `doc_max_lines`; the "Releasing" section says
  the session cuts the release through `doc-end` and drops "operator tool".
  `AGENTS.md` pointer and `CHANGELOG.md` Unreleased updated.
- Verify: `python3 -m pytest -q shared/scripts/tests`, `bash
  tests/test_codex_install.sh` and the gate pass; then the final-user path:
  run `doc-end` in this session and let it cut `v8.2.0`; `git ls-remote
  --tags origin` shows `v8.2.0` at the pushed HEAD and `gh release view
  v8.2.0` carries the former Unreleased notes. That proves Claude Code only;
  Codex and OpenCode sandboxes pushing and calling `gh` stay unverified and
  are recorded as such in the plan state.

## State (2026-10-01)

All milestones done and reviewed (brief, plan, M1, M2, final, M6 brief+plan,
M6: `APPROVED`). Delivery commits 60399bb, af4b657, 9e6e55d, b25f9ea. Remote
tags are `v8.0.0` (657d506) and `v8.1.0` (de232a0) with their GitHub
Releases; the `v0.x` tags and releases are gone. `v8.2.0` is cut by the
`doc-end` run that closes this plan, through Phase 5. Headless Codex and
OpenCode sessions reach the remote, hold the `gh` login and run the script's
checks (probed 2026-10-01 with `codex exec` and `opencode run`).
## Ownership and risk

- All milestones in-session. M4 is the only external, non-reversible step: it
  deletes two public releases that nothing pins; the saved bodies and the
  committed changelog are the rollback.
- Dependencies: M2 on M1 (the script reads the changelog); M3 on M1 and M2;
  M4 on M3; M5 on M4.
