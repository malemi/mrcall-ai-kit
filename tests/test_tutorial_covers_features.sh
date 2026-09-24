#!/usr/bin/env bash
# The tutorial is prose, and prose is what rots. This is what stops it.
#
# `ai-help` cannot lie: it reads the installed files. A tutorial explains what
# those files are FOR, which no machine can derive, so someone writes it — and
# six weeks later it describes a command that was renamed and omits two that
# were added. That is not hypothetical: this repository's own follow-up plan
# records three documents that sat wrong until an unrelated trace walked past.
#
# So: every capability the kit ships must have a section, every section must
# point at an artifact that exists, and no section may be orphaned.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
SRC="$ROOT/shared/tutorial.md"

step() { printf '\n== %s ==\n' "$*"; }

step "1. every section's proof artifact exists in the repository"
# A section claims a capability is present by naming a file. If that file is
# gone the section is describing something the kit no longer ships.
while IFS= read -r proof; do
  found=0
  for base in shared claude opencode codex; do
    # commands/x.md may ship as a command, or as a Codex skill of the same name
    name="$(basename "$proof" .md)"
    [ -e "$base/$proof" ] && found=1
    [ -e "$base/skills/$name/SKILL.md" ] && found=1
    [ -e "$base/agents/$(basename "$proof")" ] && found=1
  done
  if [ "$found" -eq 0 ]; then
    echo "FAIL: section proof '$proof' matches nothing the kit ships"; FAIL=1
  fi
done < <(grep -o 'proof: [^ ]*' "$SRC" | sed 's/proof: //')
[ "$FAIL" -eq 0 ] && echo "OK: $(grep -c 'capability:' "$SRC") sections, every proof present"
STEP1_FAIL=$FAIL

step "2. every shipped command is covered by some section"
# The failure this catches: a command is added and nobody writes its section,
# so /ai-tutorial silently teaches an incomplete kit. A section declares what it
# covers rather than the test guessing from names — several commands belong to
# one capability (doc-start, doc-create and doc-end are one harness), and a test
# that cannot express that would force a section per file, which is the
# duplication this whole file exists to avoid.
BAD=0
# Everything between `covers: ` and the closing marker. A character class would
# stop at the first hyphen and turn `doc-start` into `doc`.
COVERED="$(sed -n 's/.*covers: \(.*\) -->.*/\1/p' "$SRC" | tr ' ' '\n' | grep -v '^$')"
for f in shared/commands/*.md claude/commands/*.md opencode/commands/*.md; do
  [ -e "$f" ] || continue
  name="$(basename "$f" .md)"
  echo "$COVERED" | grep -qx "$name" \
    || { echo "FAIL: command '$name' is in no section's 'covers:' list"; BAD=1; FAIL=1; }
done
[ "$BAD" -eq 0 ] && echo "OK: $(echo "$COVERED" | wc -l) names covered"

step "3. no section is orphaned"
while IFS= read -r cap; do
  grep -q "capability: $cap " "$SRC" || { echo "FAIL: '$cap' listed twice or malformed"; FAIL=1; }
done < <(grep -o 'capability: [a-z-]*' "$SRC" | sed 's/capability: //' | sort -u)
DUP="$(grep -o 'capability: [a-z-]*' "$SRC" | sort | uniq -d)"
if [ -n "$DUP" ]; then echo "FAIL: duplicated capability: $DUP"; FAIL=1; else echo "OK"; fi

step "4. each section says what it is AND when to reach for it"
# A tutorial entry that only describes is a second inventory. The "when" is the
# half /ai-help cannot produce, and the only reason this file exists.
python3 - <<'PY' || FAIL=1
import pathlib, re, sys
src = pathlib.Path("shared/tutorial.md").read_text()
sections = re.split(r'<!-- capability: ([a-z-]+) \|[^>]*-->', src)[1:]
bad = []
for cap, body in zip(sections[::2], sections[1::2]):
    if not re.search(r'\bReach for (it|one|them)\b', body):
        bad.append(cap)
for c in bad:
    print(f"FAIL: section '{c}' never says when to reach for it")
sys.exit(1 if bad else 0)
PY
[ $? -eq 0 ] && echo "OK"

step "5. the script prints a named section, and refuses an unknown one"
cp "$SRC" "$ROOT/shared/scripts/tutorial.md"
trap 'rm -f "$ROOT/shared/scripts/tutorial.md"' EXIT
OUT="$(bash shared/scripts/ai-tutorial.sh sc 2>&1)"
echo "$OUT" | grep -q '^## ' || { echo "FAIL: a known capability printed nothing"; FAIL=1; }
OUT="$(bash shared/scripts/ai-tutorial.sh no-such-thing 2>&1)"
STEP5=0
echo "$OUT" | grep -q "No section named" || { echo "FAIL: an unknown name did not say so"; STEP5=1; FAIL=1; }
[ "$STEP5" -eq 0 ] && echo "OK"

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: the tutorial covers what the kit ships, and says when to use it"
