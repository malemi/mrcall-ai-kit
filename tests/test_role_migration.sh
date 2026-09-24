#!/usr/bin/env bash
# An installed machine migrates. An install retires the files the kit once
# installed under names it has retired, following --on-exist, and leaves every
# other file where it is. Each home is seeded in the shape of the machine the
# migration was written for; the retired names come from
# shared/roles/retired.txt, the one live file allowed to name them.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'chmod -R u+w "$TEST_ROOT" 2>/dev/null; rm -rf "$TEST_ROOT"' EXIT
RETIRED="$KIT_DIR/shared/roles/retired.txt"
fail() { echo "FAIL: $*" >&2; exit 1; }

# Whether the kit shipped a file's bytes is answered by the checkout's history.
[[ "$(git -C "$KIT_DIR" rev-parse --is-shallow-repository 2>/dev/null)" == false ]] \
  || fail "this test needs the kit's full git history"

# ── The retired entries ────────────────────────────────────────────────────
# On that machine the Claude agents are symlinks the install log records, the
# OpenCode agents are copies made before the log existed, and the one file that
# is not an agent matches no version the kit shipped.
CC_SRC=() ; CC_DST=() ; OC_SRC=() ; OC_DST=() ; LOOSE_DST=()
while IFS=$'\t' read -r src dest; do
  [[ -z "$src" || "$src" == \#* ]] && continue
  case "$dest" in
    .claude/agents/*)          CC_SRC+=("$src") ; CC_DST+=("$dest") ;;
    .config/opencode/agents/*) OC_SRC+=("$src") ; OC_DST+=("$dest") ;;
    *)                         LOOSE_DST+=("$dest") ;;
  esac
done < "$RETIRED"
(( ${#CC_DST[@]} > 0 && ${#OC_DST[@]} > 1 && ${#LOOSE_DST[@]} > 0 )) \
  || fail "retired.txt no longer has the shape this test seeds"
MODIFIED="${OC_DST[${#OC_DST[@]}-1]}"   # the one unrecorded copy an operator edited
OC_KIT=()                               # the OpenCode copies still byte-identical
for d in "${OC_DST[@]}"; do [[ "$d" == "$MODIFIED" ]] || OC_KIT+=("$d"); done
RETIRED_KIT=("${CC_DST[@]}" "${OC_KIT[@]}")   # what an install must retire
KEPT=("$MODIFIED" "${LOOSE_DST[@]}")          # what it must leave, and list
FOREIGN=(electron-app-specialist ipc-contract-reviewer python-engine-specialist release-engineer)
LEADS=(agents/build.md agents/plan.md agents/reviewer.md agents/orchestrator.md commands/orchestrator.md)
SKILL=.config/opencode/skills/orchestrator

# Commits that added or changed a repository path, oldest first.
versions() { git -C "$KIT_DIR" log --all --format=%H --diff-filter=AM --reverse -- "$1"; }

seed() { # $1 = home → the machine before the migration
  local h="$1" i c d f tmp commits log="$1/.config/mrcall-ai-kit/installed.tsv" ts=2026-08-04T09:49:00Z
  mkdir -p "$h/.claude/agents" "$h/.config/opencode/agents" "$h/.config/opencode/commands" \
    "$h/.config/opencode/skills" "$h/.config/mrcall-ai-kit"
  : > "$log"
  # Claude agents: links into the checkout, recorded. Their targets are gone from
  # the kit, so only the log can show that they are the kit's.
  for i in "${!CC_DST[@]}"; do
    ln -s "$KIT_DIR/${CC_SRC[$i]}" "$h/${CC_DST[$i]}"
    printf '%s\tsymlink\t%s\t%s\t\n' "$ts" "$h/${CC_DST[$i]}" "$KIT_DIR/${CC_SRC[$i]}" >> "$log"
  done
  # OpenCode agents: unrecorded copies, so only their bytes can show that they
  # are the kit's. Oldest and newest versions alternate: any version counts.
  for i in "${!OC_DST[@]}"; do
    mapfile -t commits < <(versions "${OC_SRC[$i]}")
    (( ${#commits[@]} > 0 )) || fail "the kit never shipped ${OC_SRC[$i]}"
    if (( i % 2 )); then c="${commits[${#commits[@]}-1]}"; else c="${commits[0]}"; fi
    git -C "$KIT_DIR" show "$c:${OC_SRC[$i]}" > "$h/${OC_DST[$i]}"
  done
  printf '\nA line the operator added.\n' >> "$h/$MODIFIED"
  for d in "${LOOSE_DST[@]}"; do printf 'Notes the operator wrote.\n' > "$h/$d"; done
  # The leads and the orchestrator command and skill, as the first versions the
  # kit shipped, recorded as copies.
  for d in "${LEADS[@]}"; do
    mapfile -t commits < <(versions "opencode/$d")
    git -C "$KIT_DIR" show "${commits[0]}:opencode/$d" > "$h/.config/opencode/$d"
    printf '%s\tcopy\t%s\t%s\t\n' "$ts" "$h/.config/opencode/$d" "$KIT_DIR/opencode/$d" >> "$log"
  done
  mapfile -t commits < <(versions opencode/skills/orchestrator/SKILL.md)
  tmp="$(mktemp -d "$TEST_ROOT/archive.XXXX")"
  git -C "$KIT_DIR" archive "${commits[0]}" opencode/skills/orchestrator | tar -x -C "$tmp"
  mv "$tmp/opencode/skills/orchestrator" "$h/$SKILL"
  printf '%s\tcopy\t%s\t%s\t\n' "$ts" "$h/$SKILL" "$KIT_DIR/opencode/skills/orchestrator" >> "$log"
  for f in "${FOREIGN[@]}"; do
    printf -- '---\ndescription: An agent the operator wrote.\nmode: subagent\n---\nBody.\n' \
      > "$h/.config/opencode/agents/$f.md"
  done
}

SEEDED=("${CC_DST[@]}" "${OC_DST[@]}" "${LOOSE_DST[@]}" "$SKILL")
for d in "${LEADS[@]}"; do SEEDED+=(".config/opencode/$d"); done
for f in "${FOREIGN[@]}"; do SEEDED+=(".config/opencode/agents/$f.md"); done

state() { # $1 = home, then paths under it → one line per path: what is there
  local h="$1" p f; shift
  for p in "$@"; do
    if [[ -L "$h/$p" ]]; then echo "$p link $(readlink "$h/$p")"
    elif [[ -d "$h/$p" ]]; then
      echo "$p dir $(cd "$h/$p" && find . -type f | LC_ALL=C sort | while read -r f; do echo "$f $(cksum < "$f")"; done | cksum)"
    elif [[ -f "$h/$p" ]]; then echo "$p file $(cksum < "$h/$p")"
    else echo "$p absent"; fi
  done
}
unchanged() { # $1 = home, then paths → each is as it was seeded
  local h="$1"; shift
  [[ "$(state "$h" "$@")" == "$(state "$TEST_ROOT/pristine" "$@")" ]]
}

run_install() { # $1 = home, $2 = --on-exist value, then extra flags → the output
  local out
  out="$(HOME="$1" "$KIT_DIR/install.sh" --environment both \
    --features doc-harness,orchestration,workers --mode copy --on-exist "$2" --yes "${@:3}" 2>&1)" \
    || fail "install --on-exist $2 failed: $out"
  printf '%s\n' "$out"
}
line() { printf "  %-8s %s" "$1" "$2"; }   # the installer's listing format
has() { grep -qF -- "$2" <<< "$1" || fail "$3: the output lacks: $2"; }
retired_lines() { awk -F'\t' '$2 == "retired"' "$1/.config/mrcall-ai-kit/installed.tsv"; }
bak_in_scan_paths() { find "$1/.claude" "$1/.config/opencode" "$1/.agents" -name '*.bak' 2>/dev/null || true; }
no_bak_in_scan_paths() { # $1 = home
  local found
  found="$(bak_in_scan_paths "$1")"
  [[ -z "$found" ]] || fail "backups left where a runtime scans: $found"
}
no_dir_bak_in_scan_paths() { # $1 = home — a directory, or a link to one, loads as a skill
  local f
  while read -r f; do
    [[ -z "$f" || ! -d "$f" ]] || fail "a directory backup is left where a runtime scans: $f"
  done <<< "$(bak_in_scan_paths "$1")"
}
assert_kept() { # $1 = home, $2 = output, $3 = case
  local d f
  for d in "${KEPT[@]}"; do has "$2" "$(line keep "$1/$d")  (not the kit's" "$3"; done
  unchanged "$1" "${KEPT[@]}" || fail "$3: a file that is not the kit's was changed"
  for f in "${FOREIGN[@]}"; do
    unchanged "$1" ".config/opencode/agents/$f.md" || fail "$3: the operator's agent $f was changed"
  done
}

# One pristine home to compare against; every case seeds its own.
seed "$TEST_ROOT/pristine"
if diff -rq "$KIT_DIR/opencode/skills/orchestrator" "$TEST_ROOT/pristine/$SKILL" >/dev/null; then
  fail "the first orchestrator skill equals the current one, so its replacement cannot be seen"
fi

# ── skip: nothing moves, and the migration is listed ───────────────────────
home="$TEST_ROOT/skip" ; seed "$home"
out="$(run_install "$home" skip)"
unchanged "$home" "${SEEDED[@]}" || fail "skip: a seeded file changed"
no_bak_in_scan_paths "$home"
for d in "${CC_DST[@]}"; do has "$out" "$(line found "$home/$d")  (recorded in the install log)" skip; done
for d in "${OC_KIT[@]}"; do has "$out" "$(line found "$home/$d")  (shipped in " skip; done
has "$out" "--on-exist skip retires nothing: overwrite or backup completes the migration." skip
has "$out" "Retired names: ${#RETIRED_KIT[@]} file(s) the kit once installed are still in place" skip
assert_kept "$home" "$out" skip
[[ -z "$(retired_lines "$home")" ]] || fail "skip: recorded a retirement"
echo "skip lists the kit's retired files and changes none: PASS"

# ── overwrite: the kit's retired files go, and nothing is backed up ────────
home="$TEST_ROOT/overwrite" ; seed "$home"
dry="$(run_install "$home" overwrite --dry-run)"
unchanged "$home" "${SEEDED[@]}" || fail "dry-run: a seeded file changed"
for d in "${CC_DST[@]}"; do has "$dry" "$(line remove "$home/$d")  (recorded in the install log)" dry-run; done
for d in "${OC_KIT[@]}"; do has "$dry" "$(line remove "$home/$d")  (shipped in " dry-run; done
assert_kept "$home" "$dry" dry-run
[[ -z "$(retired_lines "$home")" ]] || fail "dry-run: wrote the install log"
out="$(run_install "$home" overwrite)"
for d in "${RETIRED_KIT[@]}"; do
  [[ ! -e "$home/$d" && ! -L "$home/$d" ]] || fail "overwrite: $d is still there"
  has "$out" "$(line remove "$home/$d") (retired)" overwrite
done
no_bak_in_scan_paths "$home"
[[ ! -e "$home/.config/mrcall-ai-kit/backups" ]] || fail "overwrite: made a backup"
diff -r "$KIT_DIR/opencode/skills/orchestrator" "$home/$SKILL" >/dev/null || fail "overwrite: the new orchestrator skill is not installed"
assert_kept "$home" "$out" overwrite
[[ "$(retired_lines "$home" | wc -l)" -eq "${#RETIRED_KIT[@]}" ]] || fail "overwrite: expected one log line per retirement"
# A second run finds nothing more of the kit's to retire.
again="$(run_install "$home" overwrite)"
if grep -q '(retired)$' <<< "$again"; then fail "overwrite: a second run retired again"; fi
assert_kept "$home" "$again" "overwrite, second run"
# The log now says the kit has nothing under a retired name. An operator's own
# file made there afterwards is not the kit's, and stays.
printf 'An agent the operator wrote.\n' > "$home/${CC_DST[0]}"
mine="$(run_install "$home" overwrite)"
[[ -f "$home/${CC_DST[0]}" ]] || fail "overwrite: removed an operator file made after the retirement"
has "$mine" "$(line keep "$home/${CC_DST[0]}")  (not the kit's" "overwrite, operator file"
echo "overwrite removes the kit's retired files and nothing else: PASS"

# ── backup: the kit's retired files move aside; a directory leaves the scan paths
home="$TEST_ROOT/backup" ; seed "$home"
dry="$(run_install "$home" backup --dry-run)"
unchanged "$home" "${SEEDED[@]}" || fail "backup dry-run: a seeded file changed"
no_bak_in_scan_paths "$home"
[[ ! -e "$home/.config/mrcall-ai-kit/backups" ]] || fail "backup dry-run: made a backup"
for d in "${RETIRED_KIT[@]}"; do has "$dry" "$(line backup "$home/$d") -> $home/$d.bak  (" "backup dry-run"; done
out="$(run_install "$home" backup)"
for d in "${RETIRED_KIT[@]}"; do
  [[ ! -e "$home/$d" && ! -L "$home/$d" ]] || fail "backup: $d is still there"
  [[ "$(state "$home" "$d.bak" | sed 's#\.bak # #')" == "$(state "$TEST_ROOT/pristine" "$d")" ]] \
    || fail "backup: $d.bak is not the file that was there"
  has "$out" "$(line backup "$home/$d") -> $home/$d.bak (retired)" backup
done
for d in "${KEPT[@]}"; do [[ ! -e "$home/$d.bak" ]] || fail "backup: backed up $d, which is not the kit's"; done
assert_kept "$home" "$out" backup
moved="$home/.config/mrcall-ai-kit/backups/$SKILL"
[[ ! -e "$home/$SKILL.bak" && ! -L "$home/$SKILL.bak" ]] || fail "backup: the skill's backup is where OpenCode loads skills"
diff -r "$TEST_ROOT/pristine/$SKILL" "$moved" >/dev/null || fail "backup: the old skill is not at $moved"
diff -r "$KIT_DIR/opencode/skills/orchestrator" "$home/$SKILL" >/dev/null || fail "backup: the new skill is not installed"
last_bak="$(D="$home/$SKILL" awk -F'\t' '$3 == ENVIRON["D"] { b = $5 } END { print b }' "$home/.config/mrcall-ai-kit/installed.tsv")"
[[ "$last_bak" == "$moved" ]] || fail "backup: the install log records the skill's backup as '$last_bak'"
if command -v opencode >/dev/null 2>&1; then
  mkdir -p "$home/work"
  (cd "$home/work" && HOME="$home" opencode debug skill --print-logs \
    > "$TEST_ROOT/skills.json" 2> "$TEST_ROOT/skills.log") || fail "opencode debug skill failed"
  python3 - "$TEST_ROOT/skills.json" "$home/$SKILL/SKILL.md" <<'EOF' || fail "backup: OpenCode does not load exactly one orchestrator skill, the new one"
import json, sys
found = [s["location"] for s in json.load(open(sys.argv[1])) if s["name"] == "orchestrator"]
sys.exit(0 if found == [sys.argv[2]] else 1)
EOF
  # OpenCode keeps one of two same-named skills, and not always the same one,
  # so the list alone cannot show that the old skill is out of reach. Its
  # warning does: it names every duplicate it found. doc-critic, installed for
  # both runtimes, is always one, so the warning's form is checked on it first.
  grep 'duplicate skill name' "$TEST_ROOT/skills.log" | grep -q 'name=doc-critic ' \
    || fail "OpenCode no longer logs a duplicate skill in the form this test reads"
  if grep 'duplicate skill name' "$TEST_ROOT/skills.log" | grep -q 'name=orchestrator '; then
    fail "backup: OpenCode found a second orchestrator skill"
  fi
  echo "OpenCode loads one orchestrator skill, the new one: PASS"
else
  echo "SKIP: opencode is not on the PATH, so which orchestrator skill it loads is not checked"
fi
# The install log is enough to undo the migration, backups included.
HOME="$home" "$KIT_DIR/uninstall.sh" --yes --restore-backups >/dev/null
unchanged "$home" "${SEEDED[@]}" || fail "uninstall --restore-backups did not restore the seeded files"
no_bak_in_scan_paths "$home"
echo "backup moves the kit's retired files aside, and uninstall restores them: PASS"

# One generation: a second backup run replaces the directory's backup rather
# than nesting the new one inside it.
home="$TEST_ROOT/backup-twice" ; seed "$home"
run_install "$home" backup >/dev/null
run_install "$home" backup >/dev/null
diff -r "$KIT_DIR/opencode/skills/orchestrator" "$home/.config/mrcall-ai-kit/backups/$SKILL" >/dev/null \
  || fail "backup, second run: the directory's backup is not the one the first run installed"
echo "a second backup run keeps one generation of a directory: PASS"

# An operator's file made at a retired path after the retirement is not the
# kit's: uninstall leaves it, and keeps the backup that would have replaced it.
home="$TEST_ROOT/backup-then-mine" ; seed "$home"
run_install "$home" backup >/dev/null
printf 'An agent the operator wrote.\n' > "$home/${OC_KIT[0]}"
out="$(HOME="$home" "$KIT_DIR/uninstall.sh" --yes --restore-backups)"
[[ "$(cat "$home/${OC_KIT[0]}")" == "An agent the operator wrote." ]] || fail "uninstall replaced an operator file made after the retirement"
[[ "$(state "$home" "${OC_KIT[0]}.bak" | sed 's#\.bak # #')" == "$(state "$TEST_ROOT/pristine" "${OC_KIT[0]}")" ]] \
  || fail "uninstall lost the backup it could not restore"
has "$out" "KEPT backup  $home/${OC_KIT[0]}.bak" "uninstall, operator file"
echo "uninstall leaves an operator file at a retired path, and its backup: PASS"

# ── what does not count as the kit's ───────────────────────────────────────
# A recorded link the operator has pointed elsewhere, and bytes the kit shipped
# only under another path.
home="$TEST_ROOT/not-the-kits" ; seed "$home"
printf 'An agent the operator wrote.\n' > "$home/mine.md"
ln -sfn "$home/mine.md" "$home/${CC_DST[0]}"
cp "$TEST_ROOT/pristine/${OC_KIT[0]}" "$home/${LOOSE_DST[0]}"
out="$(run_install "$home" overwrite)"
[[ "$(readlink "$home/${CC_DST[0]}")" == "$home/mine.md" ]] || fail "overwrite: removed a recorded link the operator re-pointed"
has "$out" "$(line keep "$home/${CC_DST[0]}")  (not the kit's" "re-pointed link"
cmp -s "$TEST_ROOT/pristine/${OC_KIT[0]}" "$home/${LOOSE_DST[0]}" || fail "overwrite: removed bytes the kit shipped only under another path"
has "$out" "$(line keep "$home/${LOOSE_DST[0]}")  (not the kit's" "bytes from another path"
echo "a re-pointed link and another path's bytes are not the kit's: PASS"

# A copy the install log records is the kit's even after an operator edited it:
# the log identifies it, not its bytes.
home="$TEST_ROOT/recorded-copy" ; seed "$home"
printf '\nA line the operator added.\n' >> "$home/${OC_KIT[1]}"
printf '%s\tcopy\t%s\t%s\t\n' 2026-08-04T09:49:00Z "$home/${OC_KIT[1]}" "$KIT_DIR/${OC_SRC[1]}" \
  >> "$home/.config/mrcall-ai-kit/installed.tsv"
out="$(run_install "$home" overwrite)"
[[ ! -e "$home/${OC_KIT[1]}" ]] || fail "overwrite: kept a copy the install log records"
has "$out" "$(line remove "$home/${OC_KIT[1]}")  (recorded in the install log)" "recorded copy"
echo "a copy the install log records is the kit's, edited or not: PASS"

# ── symlink mode ───────────────────────────────────────────────────────────
# A link to a directory is a directory to a runtime's scan, so its backup
# leaves the scan paths too. Uninstall never puts a backup back onto a link the
# operator has re-pointed.
home="$TEST_ROOT/symlink" ; mkdir -p "$home"
for on_exist in skip backup; do
  HOME="$home" "$KIT_DIR/install.sh" --environment both --features doc-harness,orchestration,workers \
    --mode symlink --on-exist "$on_exist" --yes >/dev/null 2>&1 || fail "symlink install --on-exist $on_exist failed"
done
no_dir_bak_in_scan_paths "$home"
moved="$home/.config/mrcall-ai-kit/backups/$SKILL"
[[ -L "$moved" && "$(readlink "$moved")" == "$KIT_DIR/opencode/skills/orchestrator" ]] \
  || fail "symlink backup: the skill's link is not at $moved"
cmd="$home/.claude/commands/doc-start.md"
[[ -L "$cmd.bak" ]] || fail "symlink backup: a command's link did not move to $cmd.bak"
printf 'A command the operator wrote.\n' > "$home/mine.md"
ln -sfn "$home/mine.md" "$cmd"
out="$(printf 'y\n' | HOME="$home" "$KIT_DIR/uninstall.sh" --restore-backups)"
[[ "$(readlink "$cmd")" == "$home/mine.md" ]] || fail "uninstall replaced a link the operator re-pointed"
[[ -L "$cmd.bak" ]] || fail "uninstall lost the backup it could not restore"
has "$out" "backup stays at $cmd.bak: $cmd holds a file the kit did not put there" "uninstall preview"
has "$out" "KEPT backup  $cmd.bak" uninstall
[[ -L "$home/$SKILL" && "$(readlink "$home/$SKILL")" == "$KIT_DIR/opencode/skills/orchestrator" ]] \
  || fail "uninstall did not restore the skill's link from $moved"
echo "symlink mode backs directory links up out of reach, and uninstall spares a re-pointed link: PASS"

# ── a run for one runtime leaves the other runtime's files alone ───────────
# It neither retires them nor lists them: that runtime is not part of the run.
not_listed() { # $1 = output, $2 = home, $3 = case, then paths under the home
  local out="$1" h="$2" c="$3" d; shift 3
  for d in "$@"; do if grep -qF -- "$h/$d" <<< "$out"; then fail "$c: listed $d"; fi; done
}
home="$TEST_ROOT/claude-only" ; seed "$home"
out="$(HOME="$home" "$KIT_DIR/install.sh" --environment claude --features doc-harness \
  --mode symlink --on-exist overwrite --yes 2>&1)" || fail "claude-only install failed: $out"
for d in "${CC_DST[@]}"; do [[ ! -e "$home/$d" && ! -L "$home/$d" ]] || fail "claude-only: $d is still there"; done
unchanged "$home" "${OC_DST[@]}" "${LOOSE_DST[@]}" || fail "claude-only: changed OpenCode's files"
not_listed "$out" "$home" claude-only "${OC_DST[@]}" "${LOOSE_DST[@]}"
home="$TEST_ROOT/opencode-only" ; seed "$home"
out="$(HOME="$home" "$KIT_DIR/install.sh" --environment opencode --features orchestration,workers \
  --mode copy --on-exist overwrite --yes 2>&1)" || fail "opencode-only install failed: $out"
for d in "${OC_KIT[@]}"; do [[ ! -e "$home/$d" ]] || fail "opencode-only: $d is still there"; done
unchanged "$home" "${CC_DST[@]}" || fail "opencode-only: changed Claude Code's files"
not_listed "$out" "$home" opencode-only "${CC_DST[@]}"
echo "an install for one runtime retires and lists only that runtime's files: PASS"

# A run that installs no role agent for a runtime retires nothing there, and
# lists what it leaves.
home="$TEST_ROOT/no-roles" ; seed "$home"
out="$(HOME="$home" "$KIT_DIR/install.sh" --environment both --features orchestration \
  --mode copy --on-exist overwrite --yes 2>&1)" || fail "install without role agents failed: $out"
unchanged "$home" "${CC_DST[@]}" "${OC_DST[@]}" "${LOOSE_DST[@]}" || fail "no-roles: retired a file without installing its role"
for d in "${CC_DST[@]}"; do has "$out" "$(line found "$home/$d")  (recorded in the install log)" no-roles; done
for d in "${OC_KIT[@]}"; do has "$out" "$(line found "$home/$d")  (shipped in " no-roles; done
has "$out" "A runtime's retired files go only in a run that installs its role agents." no-roles
has "$out" "for OpenCode workers, with orchestration if its leads are installed." no-roles
has "$out" "Retired names: ${#RETIRED_KIT[@]} file(s) the kit once installed are still in place" no-roles
[[ -z "$(retired_lines "$home")" ]] || fail "no-roles: recorded a retirement"
# The shape of M6's second command: OpenCode's doc-harness, a feature that
# ships agents on Claude Code, but not OpenCode's role agents.
home="$TEST_ROOT/doc-harness-only" ; seed "$home"
out="$(HOME="$home" "$KIT_DIR/install.sh" --environment opencode --features doc-harness \
  --mode symlink --on-exist overwrite --yes 2>&1)" || fail "OpenCode doc-harness install failed: $out"
unchanged "$home" "${OC_DST[@]}" "${LOOSE_DST[@]}" || fail "doc-harness-only: retired OpenCode's files without its role agents"
for d in "${OC_KIT[@]}"; do has "$out" "$(line found "$home/$d")  (shipped in " doc-harness-only; done
echo "a run without a runtime's role agents lists its retired files and keeps them: PASS"

# ── a failed install retires nothing ───────────────────────────────────────
# Retirement runs after every install, so a run that stops partway leaves the
# old files for the next one. An unwritable kit home stops the first install.
home="$TEST_ROOT/failed-install" ; seed "$home"
chmod a-w "$home/.config/mrcall-ai-kit"
if HOME="$home" "$KIT_DIR/install.sh" --environment both --features doc-harness,orchestration,workers \
    --mode copy --on-exist overwrite --yes >/dev/null 2>&1; then
  chmod u+w "$home/.config/mrcall-ai-kit"
  echo "SKIP: this user writes into an unwritable directory, so a failed install cannot be staged"
else
  chmod u+w "$home/.config/mrcall-ai-kit"
  unchanged "$home" "${RETIRED_KIT[@]}" || fail "a failed install retired files"
  echo "a failed install retires nothing: PASS"
fi
