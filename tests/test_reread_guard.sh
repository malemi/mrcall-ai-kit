#!/usr/bin/env bash
# The re-read guard hands a finished answer back once, against a checklist.
# It runs on every turn of every session that switches it on, so the properties
# that matter are not "does it work" but "when does it refuse to act".
#
# Four of the five cases below are refusals. That is the point: a quality aid
# that can wedge a session, loop it, or cost a model pass on a two-line answer
# is worse than no quality aid. Each case was a real failure mode during
# development, not a hypothetical.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
HOOK="$ROOT/claude/scripts/reread-hook.py"

step() { printf '\n== %s ==\n' "$*"; }
LONG="$(python3 -c 'print("parola " * 200)')"

# The hook reads its flag and checklist from $HOME, so give it a sandbox one.
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT
KIT="$SANDBOX/.config/mrcall-ai-kit"
mkdir -p "$KIT"
cp "$ROOT/shared/roles/reread-checklist.md" "$KIT/reread-checklist.md"

run_hook() { # $1 = stop_hook_active, $2 = message -> stdout of the hook
  python3 -c "
import json,sys
json.dump({'stop_hook_active': $1, 'last_assistant_message': sys.argv[1]}, sys.stdout)
" "$2" | HOME="$SANDBOX" python3 "$HOOK"
}

step "1. dormant without the flag — the default state on every machine"
if [ -z "$(run_hook False "$LONG")" ]; then echo "OK"; else
  echo "FAIL: the guard acted with no flag set — it is not opt-in"; FAIL=1; fi

touch "$KIT/reread.on"

step "2. with the flag and a long answer, it blocks once and delivers the list"
OUT="$(run_hook False "$LONG")"
if echo "$OUT" | python3 -c "
import json,sys
d = json.load(sys.stdin)
assert d['decision'] == 'block', d
assert 'Did you name a check' in d['reason'], 'checklist missing from reason'
" 2>/dev/null; then echo "OK"; else
  echo "FAIL: the guard did not deliver the checklist"; FAIL=1; fi

step "3. second pass lets the turn end — without this the session loops forever"
# Measured during development: a Stop hook that blocks unconditionally pushes
# the turn back, the model finishes, it blocks again. The session had to be
# killed. `stop_hook_active` is true on the second pass and must silence it.
if [ -z "$(run_hook True "$LONG")" ]; then echo "OK"; else
  echo "FAIL: the guard blocks on the second pass — this loops a real session"; FAIL=1; fi

step "4. short answers are skipped — the second pass costs a whole model turn"
if [ -z "$(run_hook False "breve.")" ]; then echo "OK"; else
  echo "FAIL: the guard fired on a two-word answer"; FAIL=1; fi

step "5. a missing checklist fails OPEN, never closed"
mv "$KIT/reread-checklist.md" "$KIT/elsewhere.md"
if [ -z "$(run_hook False "$LONG")" ]; then echo "OK"; else
  echo "FAIL: a missing checklist blocked the turn"; FAIL=1; fi
mv "$KIT/elsewhere.md" "$KIT/reread-checklist.md"

rm -f "$KIT/reread.on"

step "6. the one-shot arms for exactly one answer and clears itself"
# `/sc <question>` is the main path. An arming that outlives its turn would be
# an always-on mode nobody switched on, so the hook spends the flag itself.
touch "$KIT/reread.once"
if [ -n "$(run_hook False "$LONG")" ] && [ ! -e "$KIT/reread.once" ]; then echo "OK"; else
  echo "FAIL: the one-shot either did not fire or survived its turn"; FAIL=1; fi

step "7. a one-shot spent on a short answer does not leak into the next question"
# The arming is spent either way. Otherwise a `/sc` whose answer came out short
# would lie in wait and fire on whatever the user asked next.
touch "$KIT/reread.once"
if [ -z "$(run_hook False "breve.")" ] && [ ! -e "$KIT/reread.once" ]; then echo "OK"; else
  echo "FAIL: a short answer left the guard armed for the next question"; FAIL=1; fi

step "8. the checklist ships, and stays short enough to be read"
LINES=$(grep -c '^[0-9]\.' "$ROOT/shared/roles/reread-checklist.md")
if [ "$LINES" -ge 1 ] && [ "$LINES" -le 8 ]; then echo "OK: $LINES items"; else
  echo "FAIL: $LINES checklist items — a list this long is injected every turn and stops being read"
  FAIL=1; fi

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: the re-read guard refuses to act in every case where it should"
