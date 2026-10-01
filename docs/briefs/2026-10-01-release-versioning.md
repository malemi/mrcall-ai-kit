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
- `shared/scripts/release.sh` refuses each listed condition with a one-line
  reason and exit 1, and `--dry-run` prints the exact tag, push and release
  commands without running them; `tests/test_release.sh` proves the refusals
  and the success path against a throwaway bare remote and a stubbed `gh`.
- The suite (`tests/test_*.sh`, `pytest tests shared/scripts/tests`) and the
  gate pass at the delivery commit.

## Assumptions

- Cutting the next real release (`v8.2.0`, the release tooling itself) is a
  separate operator decision; this work ends with a `--dry-run` on `main`.
- Codex and OpenCode operators cut releases from the same script; no
  runtime-specific command is added.
