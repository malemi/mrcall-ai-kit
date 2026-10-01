# Release versioning: one number system, tied to the harness protocol

**Date**: 2026-10-01 · **Plan**:
[`2026-10-01-release-versioning.md`](../execution-plans/2026-10-01-release-versioning.md).
Evidence verified 2026-10-01 against `main` @ de232a0, `git ls-remote --tags
origin`, and `gh release list --repo malemi/mrcall-ai-kit`.

## Problem

Until 2026-09-28 the kit had no version. Operators install from a checkout
(`git clone` + `./install.sh`) and update with `git pull` followed by a
re-run of `./install.sh`; nothing pins a point in history. The only version-like number is `harness_version` in
`docs/.doc-profile`, mirrored by `HARNESS_VERSION` in
`shared/scripts/doc-check.py`: a compatibility counter between the installed
`/doc-*` commands and a repository's `docs/` layout, bumped only when that
contract changes (seven commits took it from 1 to 8 between 2026-08-01 and
2026-09-02, stable at 8 since).

On 2026-09-28 and 2026-09-29 two Codex sessions introduced a second scheme:
annotated tags `v0.1.0` (657d506) and `v0.2.0` (de232a0), pushed to origin,
each with a published GitHub Release carrying real notes. Both sit at harness
8. Nothing in the repository reads tags, no document describes a release
process, no CHANGELOG exists, and the two tag messages even spell the project
name differently. Two numbering conventions now coexist without a rule
connecting them, which is exactly the state in which the next session invents
a third.

## Decision

One version system, semver `MAJOR.MINOR.PATCH`, with the major pinned to the
harness protocol:

- **MAJOR = `HARNESS_VERSION`.** A change to the `docs/` contract bumps
  `HARNESS_VERSION` and therefore the major; minor and patch reset to 0. A
  reader of `v9.0.0` knows every bootstrapped repository must migrate through
  `doc-create`; a reader of `v8.3.0` knows no `docs/` migration is needed:
  `git pull`, then `./install.sh` again, because the installer copies or links
  each file individually and a pull alone changes nothing installed.
- **MINOR** for a new capability or a behavior change that leaves the `docs/`
  contract untouched. **PATCH** for fixes and documentation-only releases.
- The existing tags are renumbered under this rule: `v0.1.0` becomes
  `v8.0.0` and `v0.2.0` becomes `v8.1.0`, on the same commits, with the same
  release notes; the `v0.x` tags and releases are deleted. Nothing pins them.
- The tag is annotated, its message is `mrcall-ai-kit vX.Y.Z`, and the GitHub
  Release title is the same string. No other spelling of the project name.
- Release notes live in git, in a root `CHANGELOG.md`, one section per
  version. The GitHub Release body is that section.
- **The session that ends the work cuts the release; the operator never
  does.** `doc-end` gains a final phase, driven by a new optional profile key
  `release = <command>` (the command takes `vX.Y.Z`; setting the key opts the
  repository into the `## vX.Y.Z — <date>` / `## Unreleased` changelog
  format). Before touching anything the phase skips, with a stated reason,
  when the key is absent, when `CHANGELOG.md` has no non-empty `Unreleased`
  (a non-whitespace line before the next version heading), when the branch is
  not the release branch, or when tracked files carry changes the session did
  not make. Otherwise it chooses the version by semver from the `Unreleased`
  content applied to the newest `## vX.Y.Z` heading (a repository may state
  its own rule in its docs; the kit's is the "Releasing" section), rewrites
  `Unreleased` into the version section, commits the consolidation and the
  changelog by path, pushes, and runs the profile command verbatim from the
  repository root. A refusal it may fix: a different version, a push, a
  commit of its own edits, a repair of a test this session broke. Moves it
  may never make: delete or move a tag, edit `HARNESS_VERSION` to fit,
  force-push, commit tracked changes it did not make. A refusal it cannot
  fix ends as `release: not cut — <reason>`, with the version section moved
  back under `Unreleased` and that revert committed and pushed.
- A release is cut only through `shared/scripts/release.sh vX.Y.Z`, which
  refuses to proceed when the major differs from `HARNESS_VERSION`, when the
  tag exists, when `CHANGELOG.md` has no section for the version, when
  tracked files are modified, when `HEAD` is not `main` at `origin/main`, or
  when the mechanical gate or the test suites fail. The refusal is the
  enforcement; the rule in prose is only its explanation.

## Rejected alternatives

- **A single number, `harness_version` as the kit version.** The kit changes
  when the protocol does not (Codex agents, the re-read pass, budgets), so a
  single counter either lies about compatibility or never moves.
- **Keep `0.x` and start the harness-major scheme from the next tag.** Leaves
  two conventions in the tag list forever; the inconsistency is the defect.
- **Drop tagging.** Costs nothing to keep, and a public repository benefits
  from stable points; the defect was the missing rule, not the tags.
- **The operator runs the script.** Rejected on 2026-10-01: a release
  procedure addressed to the operator is the operator doing the agents' job.
  The first delivery of this brief made that mistake; the `doc-end` phase and
  the profile key correct it.
- **Document the rule without a script.** A rule in prose is what the two
  Codex sessions did not have and would not have read; the mismatch has to be
  refused mechanically.

## Acceptance

- `git tag` lists `v8.0.0` → 657d506 and `v8.1.0` → de232a0 and no `v0.*`;
  `gh release list` shows the same two, bodies equal to the former notes; tag
  messages and release titles are exactly `mrcall-ai-kit v8.0.0` and
  `mrcall-ai-kit v8.1.0`.
- `CHANGELOG.md` holds `v8.0.0` and `v8.1.0` sections and an `Unreleased`
  section for work after `v8.1.0`.
- `docs/documentation-harness.md` has a "Releasing" section stating the rule
  and the command; `AGENTS.md` routes to `CHANGELOG.md` and the script.
- `doc-end` has a release phase that, with `release` set in the profile and
  a non-empty `Unreleased`, cuts the version itself; `docs/.doc-profile`
  accepts `release`, the gate rejects it when empty; the kit's own profile
  sets it; the first release cut this way is `v8.2.0`.
- `shared/scripts/release.sh` refuses each listed condition with a one-line
  reason and exit 1, and `--dry-run` prints the exact tag, push and release
  commands without running them; `tests/test_release.sh` proves the refusals
  and the success path against a throwaway bare remote and a stubbed `gh`.
- The suite (`tests/test_*.sh`, `pytest tests shared/scripts/tests`) and the
  gate pass at the delivery commit.

## Assumptions

- The next release (`v8.2.0`, the release tooling and the `doc-end` phase)
  is cut by this session through `doc-end`, as the end-to-end proof.
- Codex and OpenCode sessions cut releases through the same shared `doc-end`
  workflow and script; no runtime-specific command is added. Their headless
  sessions reach the remote and hold the `gh` login.
