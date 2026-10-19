# The installers run on the bash a Mac ships

## Intent

`install.sh` and `uninstall.sh` start with `#!/usr/bin/env bash` and `set -euo pipefail`. On macOS the first
`bash` on a default `PATH` is `/bin/bash`, GNU bash 3.2.57, which Apple ships and does not update. Measured on
2026-10-19 on the operator's machine (macOS, Apple Silicon):

- `install.sh ... --dry-run` under `/bin/bash` stops at line 686 with `WARNING_RUNTIMES[@]: unbound variable`:
  before bash 4.4, `"${arr[@]}"` of an empty array is an unbound-variable error under `set -u`. The same
  expansion is at line 827. Lines 287 and 316 expand arrays that cannot be empty (reached only with a
  non-empty flag value, which `read -a` splits into at least one element).
- `bash -n uninstall.sh` under `/bin/bash` fails to parse: `declare -A` (associative arrays, bash 4.0) and
  `[[ -v MODE_OF["$dest"] ]]` (bash 4.3) at lines 39, 44, 126, 136 and 145. The uninstaller has never run on a
  stock Mac.
- Under Homebrew's bash 5.3, run by hand, both work. Nothing in the kit states a bash version, and no script
  checks `BASH_VERSION`.

The operator chose (2026-10-19) to make both installers run on bash 3.2 rather than require a newer bash: an
installer should run on the system it installs onto, with nothing installed first.

## Scope

- `install.sh`: the two expansions of `WARNING_RUNTIMES`, empty unless verification warnings are activated,
  are safe under `set -u` on bash 3.2.
- `uninstall.sh`: the manifest is held in indexed arrays (one per field, one entry per unique destination,
  last line wins as now) with a lookup from destination to index; `[[ -v ... ]]` becomes that lookup. Same
  decisions, same output, same manifest rewrite: a change of representation, not of behaviour.
- A test that runs, under the oldest bash available on the machine (`/bin/bash` on macOS), every shell script
  the kit installs or runs with the `bash` first on `PATH`: both installers (parse, an install into a
  temporary `HOME`, its uninstall) and `shared/scripts/ai-help.sh` and `ai-tutorial.sh`, which the installed
  `/ai-help` and `/ai-tutorial` commands run (parse and run).
- Docs: the README states the installers' requirements, which it does not today: bash 3.2 or later and
  `python3`.

Out of scope: the kit's own development scripts (`shared/scripts/release.sh`, the tests), which run in the
kit's checkout and not on an operator's machine.

## Constraints

- No behaviour change in either installer beyond running on bash 3.2: same plan text, same files touched,
  same manifest content, on bash 5 as before (compared on the same temporary `HOME`).
- The scripts the new test runs stay within bash 3.2 from now on; the test is the gate that says so.
- `uninstall.sh` removes files: the comparison of its behaviour before and after is on a real install in a
  temporary `HOME`, never on the operator's.

## Acceptance

1. `/bin/bash -n` passes on both installers; on macOS `/bin/bash --version` is 3.2.
2. Under `/bin/bash`: `install.sh` (dry run and real, every environment and feature) into a temporary `HOME`
   exits 0; `uninstall.sh --dry-run` and `--yes` then exit 0, no path recorded in the manifest remains, and the
   manifest is empty (the directories the install created stay, empty, as they do today).
3. Under bash 5, and under `/bin/bash` after the change: the same sequence gives the same output of every step,
   the same tree after install and after uninstall, and the same manifest with its first column (the UTC
   timestamp each run writes) left out, as the scripts before the change under bash 5.
4. The new test passes, and the existing tests that exercise the installers still pass.

## Assumptions

- `python3` remains a dependency of `uninstall.sh` (the digest helper); unchanged.
