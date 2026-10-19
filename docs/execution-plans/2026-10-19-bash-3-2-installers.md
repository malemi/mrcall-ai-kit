---
status: active
---

# Plan: the installers run on the bash a Mac ships

Brief: [2026-10-19-bash-3-2-installers](../briefs/2026-10-19-bash-3-2-installers.md).

## Ownership and dependencies

One owner, one milestone; depends on nothing in flight. Files: `install.sh`, `uninstall.sh`, a new
`tests/test_bash32_scripts.sh`, `README.md` (a Requirements section), `CHANGELOG.md` (`Unreleased`),
`docs/active-context.md`.

## Design

- `install.sh` 686 and 827: `${WARNING_RUNTIMES[@]+"${WARNING_RUNTIMES[@]}"}`, the expansion bash 3.2 accepts
  for an empty array under `set -u`, identical to `"${WARNING_RUNTIMES[@]}"` when it is not empty.
- `uninstall.sh`: `order`, `MODE_AT`, `SRC_AT`, `BAK_AT`, `HASH_AT` indexed by position; `index_of <dest>`
  prints the position of a destination and fails when it is absent (a linear scan: a full install records 108
  unique destinations). The read loop updates the existing position (last line wins) or appends.
  `has_backup`, `owned_item`, `stays_occupied` look the destination up; the three registration guards use
  `index_of` where they used `[[ -v SRC_OF[...] ]]`. Every message and decision stays as it is.
- `tests/test_bash32_scripts.sh`: the bash under test is `/bin/bash` when it exists (3.2 on macOS), else the
  first `bash`; it prints which version ran, and runs the installers through it explicitly. Steps: `-n` on
  both installers, `ai-help.sh`, `ai-tutorial.sh`; install (dry run, then real, `--environment all --features
  all --mode symlink --on-exist overwrite --yes`) into a temporary `HOME` resolved with `pwd -P`; the
  installed helpers run as the commands run them, with no argument and with `all`; a reinstall with
  `--on-exist backup` (every destination twice in the manifest, each with a backup); one copied kit file
  modified; `uninstall.sh --dry-run`, then `--yes --restore-backups`. Asserts: every exit 0, the rewritten
  manifest keeps exactly the modified file's line, that file is kept, its backup is the only one left, every
  other destination is restored. A second run in a fresh `HOME` adds `--activate-verification-warnings all`,
  so `WARNING_RUNTIMES` is not empty at 686 and 827.
- Comparisons: "bash 5" is `/opt/homebrew/bin/bash` (5.3), "3.2" is `/bin/bash`, each named on the command
  line; the scripts before the change are `HEAD`'s (`git show HEAD:uninstall.sh` for the uninstaller, which
  reads only `HOME`). Three scenarios: plain, warnings activated, reinstall with backups and restore.

## Steps

### M1

- [x] Baseline with the scripts before the change, bash 5, temporary `HOME`, both runs (without and with
      `--activate-verification-warnings all`): output of each step, tree after install and after uninstall,
      manifest without its first column, the registration files' content.
- [x] The two `install.sh` expansions; the `uninstall.sh` representation.
- [x] The same sequence after the change, under bash 5 and under `/bin/bash`, compared with the baseline
      (the temporary `HOME` path normalised): acceptance 2 and 3.
- [x] `tests/test_bash32_scripts.sh` passes; the existing installer tests pass (acceptance 4).
- [x] A mutation check: with one expansion reverted, the new test fails under `/bin/bash`.
- [x] README Requirements, CHANGELOG `Unreleased`, active-context.

## Verification

A step passes when its command ran and its output is recorded under Results, not when the script exited 0.

## Rollback

Revert the commit; no data, no installed state of any machine is touched by the change itself.

## Results

### M1 (2026-10-19)

- Order: the code was written while the plan review was open, against the kit's order; the review's REVISE
  (no `--on-exist` in the command, no backup/restore path exercised, "bash 5" unnamed, helpers run from the
  checkout) is folded into the design above and measured below.
- Plain and warnings-activated runs, `HEAD` under bash 5 against the change under bash 5.3 and 3.2.57:
  identical output of every step (normalised `HOME`), tree after install and after uninstall, manifest
  without its first column, registration files (41 lines written with warnings, removed by the uninstall).
  Two runs of `HEAD` are identical to each other, so the comparison can see a difference.
- Reinstall with backups (216-line manifest), one copy modified, uninstall with restore: identical except the
  manifest file's bytes (its timestamps) and a `__pycache__` file, both of which also differ between two runs
  of `HEAD`; the remaining manifest line, the one `.bak` left and every restored path are the same.
- `tests/test_bash32_scripts.sh` under `/bin/bash` 3.2.57: PASS. With `install.sh` from `HEAD`: `FAIL: plain:
  install --dry-run`; with `uninstall.sh` from `HEAD`: `syntax error near MODE_OF["$dest"]`.
- Found on the way, not changed: the uninstaller exits 1 when `HOME` goes through a symlink
  (`docs/known-issues-and-solutions.md`), with `HEAD` as well.
- Existing shell tests, all 19, with `/opt/homebrew/bin` first on `PATH` and with `/bin` first (where
  `env bash` is 3.2.57): 38 of 38 exit 0. The Python tests that run the installers: `test_skill_path.py`
  (1 failure, 4 errors) and `test_verification_warnings_delivery.py` (4 failures) fail the same way on
  `HEAD` exported with `git archive`, under both bashes. Those 9 come from the symlinked temporary `HOME` recorded in
  `docs/known-issues-and-solutions.md`. Under 3.2 `HEAD` has 2 more errors, the bug this change fixes:
  `install.sh:686` in `test_installed_copy_and_symlink_catalog_entries`, copy and symlink.

