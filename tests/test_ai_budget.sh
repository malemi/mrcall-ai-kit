#!/usr/bin/env bash
# /ai-budget moves the installed agents between the renderings an install put
# beside the kit: it records the level, re-points each link or re-copies each
# copy, and logs every move. A copy install switches with the checkout gone.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

install_kit() { # $1=home $2=mode $3=the kit to install from
  HOME="$1" "$3/install.sh" --environment both \
    --features doc-harness,orchestration,workers --mode "$2" --on-exist skip --yes >/dev/null
}
ai_budget() { # $1=home, then the arguments → the installed script, run as the command runs it
  HOME="$1" python3 "$1/.config/mrcall-ai-kit/ai-budget.py" "${@:2}"
}
selected() { # $1=runtime $2=budget $3=role → the model models.json holds
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["runtimes"][sys.argv[2]][sys.argv[3]]["roles"][sys.argv[4]]["model"])' \
    "$KIT_DIR/shared/roles/models.json" "$1" "$2" "$3"
}
last_log() { # $1=home $2=path → the install log's last "mode<TAB>source" for the path
  D="$2" awk -F'\t' '$3 == ENVIRON["D"] { l = $2 "\t" $4 } END { print l }' "$1/.config/mrcall-ai-kit/installed.tsv"
}
state() { # $1=home → everything a switch may change
  local f
  cat "$1/.config/mrcall-ai-kit/budget" 2>/dev/null || echo "(no budget file)"
  cksum < "$1/.config/mrcall-ai-kit/installed.tsv"
  for f in "$1"/.claude/agents/*.md "$1"/.config/opencode/agents/*.md; do
    if [[ -L "$f" ]]; then echo "$f -> $(readlink "$f")"; else echo "$f $(cksum < "$f")"; fi
  done
}

check_level() { # $1=home $2=mode $3=level $4=the kit the links point into
  local pair runtime dir f name rendering
  [[ "$(cat "$1/.config/mrcall-ai-kit/budget")" == "$3" ]] || fail "$2: the budget file does not say $3"
  for pair in claude:.claude/agents opencode:.config/opencode/agents; do
    runtime="${pair%%:*}" ; dir="$1/${pair#*:}"
    for f in "$dir"/*.md; do
      name="$(basename "$f" .md)"
      rendering="$1/.config/mrcall-ai-kit/agents/$runtime/$3/$name.md"
      cmp -s "$f" "$rendering" || fail "$2: $f is not the $3 rendering"
      if [[ "$2" == symlink ]]; then
        [[ -L "$f" && "$(readlink "$f")" == "$4/$runtime/agents/$3/$name.md" ]] \
          || fail "symlink: $f does not link to the kit's $3 rendering"
        [[ "$(last_log "$1" "$f")" == "symlink"$'\t'"$4/$runtime/agents/$3/$name.md" ]] \
          || fail "symlink: the install log does not record $f as it now is"
      else
        [[ ! -L "$f" ]] || fail "copy: $f became a link"
        [[ "$(last_log "$1" "$f")" == "copy"$'\t'"$rendering" ]] \
          || fail "copy: the install log does not record $f as a copy of its $3 rendering"
      fi
    done
  done
}

# ── copy mode: a switch reads nothing from the checkout (AC9) ─────────────
home="$TEST_ROOT/copy-home" ; mkdir -p "$home"
mkdir -p "$TEST_ROOT/kit-copy"
tar -C "$KIT_DIR" --exclude=.git -cf - . | tar -C "$TEST_ROOT/kit-copy" -xf -
install_kit "$home" copy "$TEST_ROOT/kit-copy"
mv "$TEST_ROOT/kit-copy" "$TEST_ROOT/kit-moved-away"
for level in low high medium; do
  ai_budget "$home" "$level" > "$TEST_ROOT/out" || fail "copy: switching to $level failed with the checkout gone"
  check_level "$home" copy "$level" ""
done
echo "copy mode switches between installed renderings with the checkout gone: PASS"

python3 - "$home/.config/mrcall-ai-kit/installed.tsv" <<'CHECK'
from pathlib import Path
import hashlib, json, stat, sys
latest={}
for line in Path(sys.argv[1]).read_text().splitlines():
    fields=line.split('\t')
    latest[fields[2]]=fields
for name,fields in latest.items():
    path=Path(name)
    if path.parent.name == 'agents' and path.suffix == '.md':
        records=[[".",stat.S_IFREG,stat.S_IMODE(path.stat().st_mode),hashlib.sha256(path.read_bytes()).hexdigest()]]
        expected=hashlib.sha256(json.dumps(records,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
        assert len(fields)==6 and fields[5]==expected, name
print('budget switch retains exact copied-agent ownership digest: PASS')
CHECK


# ── symlink mode: a switch re-points each link into the checkout ──────────
home="$TEST_ROOT/symlink-home" ; mkdir -p "$home"
install_kit "$home" symlink "$KIT_DIR"
ai_budget "$home" high > "$TEST_ROOT/out"
check_level "$home" symlink high "$KIT_DIR"
grep -q '^Budget: high (was medium)$' "$TEST_ROOT/out" || fail "symlink: the switch does not say what changed"
grep -q '^Claude Code: the next delegation runs on these models' "$TEST_ROOT/out" \
  || fail "the switch does not say when Claude Code picks it up"
grep -q '^OpenCode: an OpenCode started from now on runs on these models; one already running keeps its old models, in new sessions too' "$TEST_ROOT/out" \
  || fail "the switch does not say when OpenCode picks it up"
if command -v opencode >/dev/null 2>&1; then
  mkdir -p "$home/work"
  for level in low high; do
    ai_budget "$home" "$level" >/dev/null
    got="$(cd "$home/work" && HOME="$home" opencode debug agent verify < /dev/null 2>/dev/null \
      | python3 -c 'import json, sys; m = json.load(sys.stdin)["model"]; print(m["providerID"] + "/" + m["modelID"])')"
    [[ "$got" == "$(selected opencode "$level" verify)" ]] \
      || fail "after ai-budget $level, OpenCode resolves verify to $got"
  done
  echo "OpenCode resolves verify to the switched level's model: PASS"
else
  echo "SKIP: opencode is not on the PATH, so the model OpenCode resolves is not checked"
fi
echo "symlink mode re-points each agent and logs it: PASS"

# ── an unknown level, or a missing rendering, changes nothing ─────────────
before="$(state "$home")"
if ai_budget "$home" lavish > "$TEST_ROOT/out" 2>&1; then fail "an unknown level was accepted"; fi
grep -q "'lavish' is not a budget; use one of low, medium, high. Nothing was changed." "$TEST_ROOT/out" \
  || fail "an unknown level is refused without saying why"
[[ "$(state "$home")" == "$before" ]] || fail "an unknown level changed something"
mv "$home/.config/mrcall-ai-kit/agents/claude/medium/execute.md" "$TEST_ROOT/set-aside"
if ai_budget "$home" medium > "$TEST_ROOT/out" 2>&1; then fail "a switch with a rendering missing went ahead"; fi
grep -q "execute.md: no medium rendering" "$TEST_ROOT/out" || fail "a missing rendering is not named"
[[ "$(state "$home")" == "$before" ]] || fail "a switch with a rendering missing changed something"
mv "$TEST_ROOT/set-aside" "$home/.config/mrcall-ai-kit/agents/claude/medium/execute.md"
echo "an unknown level and a missing rendering change nothing, and say why: PASS"

# ── agents linked into a checkout that is gone cannot switch ──────────────
# The script is a copy here and the OpenCode agents are links: mixed modes, as
# separate runs install them. (A symlink install's script is itself a link into
# the checkout, so it goes with it.)
gone="$TEST_ROOT/gone-home" ; mkdir -p "$gone" "$TEST_ROOT/kit-linked"
tar -C "$KIT_DIR" --exclude=.git -cf - . | tar -C "$TEST_ROOT/kit-linked" -xf -
HOME="$gone" "$TEST_ROOT/kit-linked/install.sh" --environment claude --features doc-harness \
  --mode copy --on-exist skip --yes >/dev/null
HOME="$gone" "$TEST_ROOT/kit-linked/install.sh" --environment opencode --features orchestration,workers \
  --mode symlink --on-exist skip --yes >/dev/null
mv "$TEST_ROOT/kit-linked" "$TEST_ROOT/kit-linked-moved"
before_gone="$(state "$gone")"
if ai_budget "$gone" low > "$TEST_ROOT/out" 2>&1; then fail "a switch into a missing checkout went ahead"; fi
grep -q "its low rendering links to $TEST_ROOT/kit-linked/.*, which is gone" "$TEST_ROOT/out" \
  || fail "a missing checkout is not named"
[[ "$(state "$gone")" == "$before_gone" ]] || fail "a switch into a missing checkout changed something"
echo "agents linked into a checkout that is gone refuse to switch, and say why: PASS"

# ── a file the operator put at an agent's path is left alone ─────────────
printf -- '---\nname: verify\ndescription: mine\nmodel: my-own\n---\n' > "$TEST_ROOT/mine.md"
ln -sfn "$TEST_ROOT/mine.md" "$home/.claude/agents/verify.md"
ai_budget "$home" low > "$TEST_ROOT/out"
[[ "$(readlink "$home/.claude/agents/verify.md")" == "$TEST_ROOT/mine.md" ]] || fail "the operator's verify was replaced"
grep -qE "^  verify +my-own +\(not the kit's file any more: left alone\)$" "$TEST_ROOT/out" \
  || fail "the operator's file is not listed as left alone"
[[ "$(readlink "$home/.claude/agents/execute.md")" == "$KIT_DIR/claude/agents/low/execute.md" ]] \
  || fail "the kit's other agents did not switch"
echo "an operator's file at an agent's path is left alone and listed: PASS"

# ── what an --on-exist backup install moved aside still comes back ───────
# A switch replaces the kit's file, not the operator's: the backup the install
# recorded stays the one uninstall --restore-backups puts back.
for mode in copy symlink; do
  home="$TEST_ROOT/$mode-backup-home" ; mkdir -p "$home/.claude/agents"
  printf -- '---\nname: verify\ndescription: mine\nmodel: my-own\n---\nmine\n' > "$home/.claude/agents/verify.md"
  cp "$home/.claude/agents/verify.md" "$TEST_ROOT/$mode-mine"
  HOME="$home" "$KIT_DIR/install.sh" --environment claude --features doc-harness \
    --mode "$mode" --on-exist backup --yes >/dev/null
  ai_budget "$home" high >/dev/null
  HOME="$home" "$KIT_DIR/uninstall.sh" --yes --restore-backups >/dev/null
  cmp -s "$home/.claude/agents/verify.md" "$TEST_ROOT/$mode-mine" \
    || fail "$mode: after a switch, uninstall --restore-backups did not put the operator's verify.md back"
done
echo "after a switch, uninstall still restores what a backup install moved aside: PASS"

# ── the command's form puts every outcome on stdout ───────────────────────
# OpenCode hands a command only the stdout of its shell line, and ignores the
# exit status, so the form /ai-budget runs must say everything there.
home="$TEST_ROOT/report-home" ; mkdir -p "$home"
install_kit "$home" symlink "$KIT_DIR"
for runtime_dir in .claude/commands .config/opencode/commands; do
  grep -qF 'ai-budget.py" --report $ARGUMENTS`' "$home/$runtime_dir/ai-budget.md" \
    || fail "the installed $runtime_dir/ai-budget.md does not run the script with --report"
done
before="$(state "$home")"
report() { # $1=what, then the arguments → stdout must say it, stderr stay empty, exit 0
  local what="$1"; shift
  ai_budget "$home" --report "$@" > "$TEST_ROOT/out" 2> "$TEST_ROOT/err" || fail "--report $*: exited non-zero"
  [[ ! -s "$TEST_ROOT/err" ]] || fail "--report $*: wrote to stderr"
  grep -q "$what" "$TEST_ROOT/out" || fail "--report $*: stdout does not say '$what'"
}
report "'extreme' is not a budget; use one of low, medium, high. Nothing was changed." extreme
report "usage: ai-budget" low high
mv "$home/.config/mrcall-ai-kit/agents/opencode/high/plan.md" "$TEST_ROOT/parked"
report "plan.md: no high rendering" high
grep -q -- "--on-exist overwrite" "$TEST_ROOT/out" || fail "--report: the refusal's advice is missing"
mv "$TEST_ROOT/parked" "$home/.config/mrcall-ai-kit/agents/opencode/high/plan.md"
[[ "$(state "$home")" == "$before" ]] || fail "--report: a refused switch changed something"
report "^Budget: medium"
echo lavish > "$home/.config/mrcall-ai-kit/budget"
report "says 'lavish', which is not one of low, medium, high"
rm "$home/.config/mrcall-ai-kit/budget"
echo "the command's form reports every outcome on stdout: PASS"

# ── the status ─────────────────────────────────────────────────────────────
home="$TEST_ROOT/status-home" ; mkdir -p "$home"
install_kit "$home" symlink "$KIT_DIR"
ai_budget "$home" > "$TEST_ROOT/out"
grep -q '^Budget: medium (the default: .* is absent)$' "$TEST_ROOT/out" || fail "status: the default budget is not shown"
for role in execute verify reviewer; do
  grep -qE "^  $role +$(selected claude medium "${role/reviewer/review}")\$" "$TEST_ROOT/out" \
    || fail "status: Claude Code's $role does not show its medium model"
done
ai_budget "$home" low >/dev/null
ai_budget "$home" > "$TEST_ROOT/out"
grep -q "^Budget: low ($home/.config/mrcall-ai-kit/budget)\$" "$TEST_ROOT/out" || fail "status: the switched budget is not shown"
grep -qE "^  verify +$(selected opencode low verify)\$" "$TEST_ROOT/out" || fail "status: OpenCode's verify does not show its low model"
echo "the status shows the budget and each agent's model: PASS"
