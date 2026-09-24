#!/usr/bin/env bash
# The kit retired its model-named agents and the model table the orchestrator
# read. shared/roles/retired.txt is the one live file allowed to name them —
# the installer needs the names to retire them from a machine — and this gate
# fails when any other live file names one again.
#
# History keeps its names: briefs, plans, the context archive and the incident
# records describe what was true when they were written.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
RETIRED="shared/roles/retired.txt"

patterns=() ; agents=()
while IFS=$'\t' read -r src _dest; do
  [[ -z "$src" || "$src" == \#* ]] && continue
  patterns+=(-e "$(basename "$src" .md)")
  [[ "$src" == *.md && "$src" != */* ]] && patterns+=(-e "$(basename "$src")")
  [[ "$src" == */agents/* ]] && agents+=("$(basename "$src" .md)")
done < "$RETIRED"
# The permission pattern that granted the retired agents is their common name
# prefix plus `*`. It is derived rather than written here, so that this file
# names nothing retired either.
prefix="${agents[0]}"
for a in "${agents[@]}"; do
  while [[ "${a#"$prefix"}" == "$a" ]]; do prefix="${prefix%?}"; done
done
[[ -n "$prefix" ]] && patterns+=(-e "$prefix*")

# Fixed strings, so the permission pattern matches itself and not every word
# that shares its prefix. Untracked files count too: a new file is live the
# moment it exists.
hits="$(git grep --untracked -n -F "${patterns[@]}" -- . \
  ':!docs/briefs' ':!docs/execution-plans' ':!docs/active-context-archive.md' \
  ':!docs/known-issues-and-solutions.md' ":!$RETIRED")"
rc=$?
# git grep exits 1 for no match and above 1 for an error: outside a git
# checkout it prints "fatal" and matches nothing, which is not a pass.
if (( rc > 1 )); then
  echo "FAIL: git grep could not run (exit $rc)"
  exit 1
fi
if [[ -n "$hits" ]]; then
  echo "FAIL: live files name something the kit retired:"
  echo "$hits"
  exit 1
fi
echo "OK: no live file names a retired agent or file ($(( ${#patterns[@]} / 2 )) names checked)"
