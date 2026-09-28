# Repair the installed documentation checks

**Date:** 2026-09-28. **Trigger:** semantic review during `$doc-end` after
commit `4f5d11c`.

## Problem and evidence

Both `shared/commands/doc-end.md` and its Codex mirror require
`shared/scripts/doc-keywords.py --repo . --json`. The installer distributes
`doc-check.py` with `doc-harness`, but omits `doc-keywords.py`. An installed
`doc-end` running in an ordinary project therefore names a path that exists
only in the kit checkout. The script also ignores the exit status of Git's
ancestor check, so an invalid `doc_baseline_commit` never takes the documented
recent-commit fallback. Its `git log --oneline` input treats abbreviated commit
hashes as keywords; the first audit output included hash fragments rather than
document topics.

The named-capability path of `shared/scripts/ai-tutorial.sh` prints a section
without testing its installed proof artifact, although the tutorial and script
promise that readers see only capabilities they have. The current tutorial
test asks for `sc` without installing its proof, so it approves that defect.

## Decision

Install `doc-keywords.py` once under the kit-global home whenever
`doc-harness` is selected. Make both `doc-end` runtime texts invoke that
installed path. Make the script surface invalid Git commands while treating a
valid non-ancestor result as a reason to fall back. Select the baseline range
only when the baseline is an ancestor, and fall back to recent
commits in short repositories as well. Read commit subjects without their
hashes. Honor the existing `--docs-only` option by excluding the root README.

Make `ai-tutorial.sh` check the proof path for named capabilities too. Give a
known but uninstalled name a distinct answer from an unknown name. Update the
tutorial test to exercise both cases in a temporary HOME.

## Rejected alternatives

- Requiring every target repository to contain `shared/scripts/` would turn a
  globally installed command into a checkout-dependent command.
- Merely changing the workflow's fallback wording would leave invalid
  baselines silently producing the wrong range.
- Merely narrowing the tutorial's promise would teach users capabilities
  absent from their installation when they request one by name.

## Verification boundary

Use temporary-HOME copy and symlink installs to prove the keyword checker is
in the manifest, runs from an unrelated working directory, and is removed by
`uninstall.sh`. Use temporary Git repositories to exercise valid and invalid
baselines and check that commit hashes are absent from keywords. Run the
installed tutorial script with and without a named capability's proof. Then
run the repository test and documentation gates. These CLI checks establish
the behavior the installed workflows use; they do not claim a new Claude Code
or OpenCode session was run.
