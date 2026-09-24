#!/usr/bin/env bash
# `--help` is the only documentation most people will ever read, and it drifts
# silently: a flag gains a value, a feature is added, and the help still
# describes the installer as it was.
#
# This is not hypothetical. `--on-exist` listed `skip|overwrite|backup` in its
# usage line and then said only "what to do when a target file already exists",
# so the operator could not tell what `backup` did without reading the source —
# and neither could the session that recommended it. The `reread` feature was
# added to the `--features` list with no section describing it at all.
#
# So: every flag the parser accepts is explained, every value it accepts is
# explained, and every feature is described.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
HELP="$(./install.sh --help 2>&1)"

step() { printf '\n== %s ==\n' "$*"; }

step "1. every flag the parser accepts has its own explanation line"
# Appearing in the usage line is not enough — that names a flag without saying
# what it does, which is the drift this gate exists to catch.
BAD=0
while read -r flag; do
  # An explanation line starts with the flag and a colon.
  echo "$HELP" | grep -qE "^ +${flag}:" \
    || { echo "FAIL: $flag is parsed but never explained (usage line does not count)"; BAD=1; FAIL=1; }
done < <(grep -oE '^\s+--[a-z-]+\|?-?[a-z]?\)' install.sh | tr -d ' )' | sed 's/|.*//' | sort -u)
[ "$BAD" -eq 0 ] && echo "OK"

step "2. every value an enum flag accepts is explained, not just listed"
# The --on-exist failure exactly: three values in the usage line, none defined.
BAD=0
for pair in "on-exist:skip overwrite backup" "mode:symlink copy"; do
  flag="${pair%%:*}"; values="${pair#*:}"
  # Drop the terminating line: the range ends ON the next flag, and matching a
  # value inside a NEIGHBOUR's text is a false negative. Found the hard way —
  # `--yes: skip the final confirmation` made `--on-exist`'s undocumented
  # `skip` look documented.
  body="$(echo "$HELP" | sed -n "/^ *--${flag}:/,/^ *--[a-z]/p" | head -n -1)"
  for v in $values; do
    echo "$body" | grep -q "$v" \
      || { echo "FAIL: --$flag accepts '$v' and never says what it does"; BAD=1; FAIL=1; }
  done
done
[ "$BAD" -eq 0 ] && echo "OK"

step "3. every feature in --features has a block under 'What gets installed'"
# The failure this catches: a feature is added to the list and nobody writes
# its block, so it is installable and undocumented.
BAD=0
FEATURES="$(echo "$HELP" | sed -n '/^ *--features:/,/^ *--[a-z]*-*[a-z]*:/p' \
  | tr ',' '\n' | grep -oE '\b(doc-harness|orchestration|workers|migrate|router|reread|scope-guard|shortcuts)\b' | sort -u)"
for f in $FEATURES; do
  echo "$HELP" | grep -qE "^  ${f} +\[" \
    || { echo "FAIL: feature '$f' is offered but has no block describing it"; BAD=1; FAIL=1; }
done
[ "$BAD" -eq 0 ] && echo "OK: $(echo "$FEATURES" | wc -w) features, each described"

step "4. the feature list matches what the installer actually implements"
# A feature the help offers but the installer ignores would install nothing and
# say so nowhere.
BAD=0
for f in $FEATURES; do
  grep -q "want_feature ${f}\b" install.sh \
    || { echo "FAIL: help offers '$f' but the installer never reads it"; BAD=1; FAIL=1; }
done
while read -r impl; do
  echo "$FEATURES" | grep -qx "$impl" \
    || { echo "FAIL: installer implements '$impl' but --help never offers it"; BAD=1; FAIL=1; }
done < <(grep -oE 'want_feature [a-z-]+' install.sh | awk '{print $2}' | sort -u)
[ "$BAD" -eq 0 ] && echo "OK"

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: --help explains every flag, every value, and every feature"
