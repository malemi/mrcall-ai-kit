#!/usr/bin/env bash
# The agent definitions are composed from shared/roles/ and must not be edited
# by hand. This is the gate that makes that true rather than aspirational: it
# fails when a shipped agent file disagrees with the source it was built from.
#
# Without it, the single source of truth is a convention, and a convention is
# what the 836 duplicated lines this replaced were made of.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

step() { printf '\n== %s ==\n' "$*"; }

step "1. every generated agent and the role skill match shared/roles/"
if python3 shared/scripts/build-agents.py --check; then
  echo "OK"
else
  echo "FAIL: a generated file was hand-edited, or shared/roles/ changed without regenerating"
  FAIL=1
fi

step "2. regenerating is a no-op (the generator is deterministic)"
# In a scratch copy: regenerating the checkout itself would overwrite the very
# hand edit step 1 just reported, and then blame it on the generator.
SCRATCH="$(mktemp -d)"
cp -r shared claude opencode "$SCRATCH"/
outputs() { (cd "$SCRATCH" && find claude/agents opencode/agents shared/skills/kit-role-rules -type f -exec md5sum {} + | sort); }
python3 "$SCRATCH/shared/scripts/build-agents.py" >/dev/null
FIRST="$(outputs)"
python3 "$SCRATCH/shared/scripts/build-agents.py" >/dev/null
SECOND="$(outputs)"
rm -rf "$SCRATCH"
if [ "$FIRST" = "$SECOND" ]; then
  echo "OK"
else
  echo "FAIL: two runs of the generator wrote different files — it is not deterministic"
  FAIL=1
fi

step "3. every agent carries the rules, by one route or the other"
# Claude agents get them via the preloaded skill; OpenCode agents inline,
# because that runtime has no include. A file with neither is a worker with no
# rules at all, which is the failure this whole layer exists to prevent.
for f in claude/agents/*/*.md; do
  grep -q '^skills: kit-role-rules$' "$f" || { echo "FAIL: $f names no role skill"; FAIL=1; }
done
# Each OpenCode agent must carry exactly the shared blocks agents.json records
# for it, so this fails if a regeneration ever silently adds a rule to an agent
# or takes one away.
python3 - <<'PY' || FAIL=1
import json, pathlib, sys
m = json.loads(pathlib.Path("shared/roles/agents.json").read_text())
budgets = json.loads(pathlib.Path("shared/roles/models.json").read_text())["runtimes"]["opencode"]
bad = []
for e in m.values():
    if e["runtime"] != "opencode":
        continue
    for budget in budgets:
        src = e["src"].format(budget=budget)
        body = pathlib.Path(src).read_text()
        for h in ("## Proportional execution", "## Report budget", "## Delivery contract"):
            if (h in e["blocks"]) != (h in body):
                bad.append(f"{src}: {h} " + ("missing" if h in e["blocks"] else "added"))
for b in bad:
    print(f"FAIL: {b}")
sys.exit(1 if bad else 0)
PY
[ "$FAIL" -eq 0 ] && echo "OK: $(ls claude/agents/*/*.md | wc -l) via skill, $(ls opencode/agents/*/*.md | wc -l) inline, each with the blocks agents.json records"

step "4. the skill Claude preloads actually exists where install.sh ships it"
if [ -f shared/skills/kit-role-rules/SKILL.md ]; then echo "OK"; else
  echo "FAIL: agents name kit-role-rules but the skill is not in shared/skills/"; FAIL=1
fi

step "5. no stub names a model, and every rendering names the one models.json holds"
# The model is data the refresh writes, never a name someone types into a stub:
# a stub with a model would be a second knob. Every budget of every agent has a
# rendering, and its one model line is models.json's choice for its role.
python3 - <<'PY' || FAIL=1
import json, pathlib, re, sys
agents = json.loads(pathlib.Path("shared/roles/agents.json").read_text())
selection = json.loads(pathlib.Path("shared/roles/models.json").read_text())["runtimes"]
bad = []
def frontmatter(path):
    return path.read_text().split("\n---", 1)[0]
for stub in sorted(pathlib.Path("shared/roles/agents").glob("*.md")):
    if re.search(r"^model:", frontmatter(stub), re.M):
        bad.append(f"{stub} names a model")
count = 0
for e in agents.values():
    for budget, outcome in selection[e["runtime"]].items():
        path = pathlib.Path(e["src"].format(budget=budget))
        want = outcome["roles"][e["role"]]["model"]
        found = re.findall(r"^model: (.*)$", frontmatter(path), re.M) if path.is_file() else ["no file"]
        if found != [want]:
            bad.append(f"{path}: model {found}, models.json holds {want!r}")
        count += 1
for b in bad:
    print(f"FAIL: {b}")
print(f"OK: {count} renderings, each naming models.json's model" if not bad else "", end="")
sys.exit(1 if bad else 0)
PY
echo

step "6. an agent file no source renders is caught, and regenerating removes it"
# The flat <runtime>/agents/<name>.md files are gone. One left behind, or put
# back by hand, would ship a model no refresh chose.
SCRATCH="$(mktemp -d)"
cp -r shared claude opencode "$SCRATCH"/
cp claude/agents/medium/execute.md "$SCRATCH/claude/agents/execute.md"
# The output is captured first: under pipefail, `--check | grep -q` would fail
# on --check's own exit status, which is 1 exactly when it finds the file.
CHECK="$(python3 "$SCRATCH/shared/scripts/build-agents.py" --check 2>&1)"
if grep -q 'claude/agents/execute.md' <<< "$CHECK"; then
  GEN="$(python3 "$SCRATCH/shared/scripts/build-agents.py")"
  if [ -e "$SCRATCH/claude/agents/execute.md" ]; then
    echo "FAIL: regenerating left the unrendered file in place"; FAIL=1
  elif ! grep -q '^removed claude/agents/execute.md' <<< "$GEN"; then
    echo "FAIL: regenerating removed a file without naming it"; FAIL=1
  else
    echo "OK"
  fi
else
  echo "FAIL: --check does not name an agent file no source renders"; FAIL=1
fi
rm -rf "$SCRATCH"

step "7. the generator refuses a stub that names a model"
SCRATCH="$(mktemp -d)"
cp -r shared claude opencode "$SCRATCH"/
sed -i 's/^description:/model: hand-picked\ndescription:/' "$SCRATCH/shared/roles/agents/claude--execute.md"
OUT="$(python3 "$SCRATCH/shared/scripts/build-agents.py" 2>&1)"; RC=$?
if [ "$RC" -ne 0 ] && grep -q 'claude--execute.md names a model' <<< "$OUT"; then
  echo "OK"
else
  echo "FAIL: a stub with a model was rendered (exit $RC)"; FAIL=1
fi
rm -rf "$SCRATCH"

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: agents are in sync with shared/roles/"
