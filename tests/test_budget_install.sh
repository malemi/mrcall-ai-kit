#!/usr/bin/env bash
# Every kit agent ships once per budget. An install puts all three renderings of
# each agent it installs in the kit's home, and the one for the machine's budget
# where the runtime reads agents. The budget is ~/.config/mrcall-ai-kit/budget,
# and medium when that file is absent.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
BUDGETS=(low medium high)

install_kit() { # $1=home $2=mode
  HOME="$1" "$KIT_DIR/install.sh" --environment both \
    --features doc-harness,orchestration,workers --mode "$2" --on-exist skip --yes
}

placed_as() { # $1=installed path $2=the checkout's rendering $3=mode
  cmp -s "$1" "$2" || fail "$1 is not $2"
  if [[ "$3" == symlink ]]; then
    [[ -L "$1" && "$(readlink "$1")" == "$2" ]] || fail "$1 is not a link to $2"
  else
    [[ ! -L "$1" ]] || fail "$1 is a link in copy mode"
  fi
}

check_home() { # $1=home $2=mode $3=the budget the runtimes must read
  local pair runtime dir f name b count
  for pair in claude:.claude/agents:3 opencode:.config/opencode/agents:6; do
    IFS=: read -r runtime dir count <<< "$pair"
    [[ "$(ls "$1/$dir"/*.md | wc -l)" -eq "$count" ]] || fail "$2: expected $count agents in $dir"
    for f in "$1/$dir"/*.md; do
      name="$(basename "$f")"
      placed_as "$f" "$KIT_DIR/$runtime/agents/$3/$name" "$2"
      for b in "${BUDGETS[@]}"; do
        placed_as "$1/.config/mrcall-ai-kit/agents/$runtime/$b/$name" "$KIT_DIR/$runtime/agents/$b/$name" "$2"
      done
    done
  done
}

# OpenCode resolves an installed agent without calling a model, which shows the
# model string it would run. It does not show that the model can be called.
opencode_model() { # $1=home $2=agent → provider/model as OpenCode resolves it
  mkdir -p "$1/work"
  (cd "$1/work" && HOME="$1" opencode debug agent "$2" < /dev/null 2>/dev/null) \
    | python3 -c 'import json, sys; m = json.load(sys.stdin)["model"]; print(m["providerID"] + "/" + m["modelID"])'
}
selected() { # $1=runtime $2=budget $3=role → the model models.json holds
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["runtimes"][sys.argv[2]][sys.argv[3]]["roles"][sys.argv[4]]["model"])' \
    "$KIT_DIR/shared/roles/models.json" "$1" "$2" "$3"
}

for mode in copy symlink; do
  home="$TEST_ROOT/$mode-default" ; mkdir -p "$home"
  install_kit "$home" "$mode" > "$TEST_ROOT/out" || fail "$mode: install failed"
  check_home "$home" "$mode" medium
  grep -q "read the medium budget's renderings (the default" "$TEST_ROOT/out" \
    || fail "$mode: the install does not say which budget the runtimes read"

  home="$TEST_ROOT/$mode-low" ; mkdir -p "$home/.config/mrcall-ai-kit"
  echo low > "$home/.config/mrcall-ai-kit/budget"
  install_kit "$home" "$mode" >/dev/null || fail "$mode: install with a low budget failed"
  check_home "$home" "$mode" low
done
echo "each mode places the machine's budget at the runtime paths, and every budget in the kit's home: PASS"

# The router installs Claude Code's role agents on its own when doc-harness is
# not selected, and places them the same way.
for mode in copy symlink; do
  home="$TEST_ROOT/$mode-router" ; mkdir -p "$home/.config/mrcall-ai-kit"
  echo high > "$home/.config/mrcall-ai-kit/budget"
  HOME="$home" "$KIT_DIR/install.sh" --environment claude --features router \
    --mode "$mode" --on-exist skip --yes >/dev/null || fail "$mode: router install failed"
  [[ "$(ls "$home/.claude/agents"/*.md | wc -l)" -eq 3 ]] || fail "$mode: router did not install the three roles"
  for f in "$home/.claude/agents"/*.md; do
    name="$(basename "$f")"
    placed_as "$f" "$KIT_DIR/claude/agents/high/$name" "$mode"
    for b in "${BUDGETS[@]}"; do
      placed_as "$home/.config/mrcall-ai-kit/agents/claude/$b/$name" "$KIT_DIR/claude/agents/$b/$name" "$mode"
    done
  done
done
echo "the router alone places Claude Code's roles by budget, with every budget in the kit's home: PASS"

if command -v opencode >/dev/null 2>&1; then
  for budget in medium low; do
    home="$TEST_ROOT/symlink-default" ; [[ "$budget" == low ]] && home="$TEST_ROOT/symlink-low"
    got="$(opencode_model "$home" verify)" || fail "opencode debug agent verify failed"
    want="$(selected opencode "$budget" verify)"
    [[ "$got" == "$want" ]] || fail "OpenCode resolves verify to $got at $budget; models.json holds $want"
  done
  echo "OpenCode resolves verify to models.json's model for the budget: PASS"
else
  echo "SKIP: opencode is not on the PATH, so the model OpenCode resolves is not checked"
fi

# The help's inventory names the agents, not the budget directories.
help="$("$KIT_DIR/install.sh" --help)"
grep -q 'agents:     execute, reviewer, verify' <<< "$help" \
  || fail "--help does not list the Claude Code agents by name"
echo "--help lists the agents by name: PASS"

# A budget file that names no budget stops the install before it writes.
home="$TEST_ROOT/unknown" ; mkdir -p "$home/.config/mrcall-ai-kit"
echo lavish > "$home/.config/mrcall-ai-kit/budget"
if install_kit "$home" symlink > "$TEST_ROOT/out" 2>&1; then fail "an unknown budget was accepted"; fi
grep -q "says 'lavish'; a budget is one of: low medium high" "$TEST_ROOT/out" \
  || fail "an unknown budget is refused without saying why"
[[ ! -e "$home/.claude" && ! -e "$home/.config/opencode" && ! -e "$home/.config/mrcall-ai-kit/installed.tsv" ]] \
  || fail "an unknown budget still wrote files"
# A run that places no agent does not depend on the budget.
HOME="$home" "$KIT_DIR/install.sh" --environment claude --features shortcuts \
  --mode symlink --on-exist skip --yes >/dev/null 2>&1 || fail "an unknown budget stopped an install that places no agent"
[[ -e "$home/.claude/commands/nr.md" ]] || fail "the shortcuts install did not run"
echo "an unknown budget stops only the installs that place agents, and says why: PASS"

# Both placements are in the install log, so uninstall removes them all.
home="$TEST_ROOT/copy-default"
HOME="$home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
left="$(find "$home/.claude/agents" "$home/.config/opencode/agents" "$home/.config/mrcall-ai-kit/agents" -type f 2>/dev/null | wc -l)"
[[ "$left" -eq 0 ]] || fail "uninstall left $left agent files"
echo "uninstall removes every rendering it installed: PASS"
