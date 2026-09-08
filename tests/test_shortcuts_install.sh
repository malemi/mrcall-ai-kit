#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# A real install (not --dry-run, which writes no manifest lines and so cannot
# prove the uninstall half) under a sandboxed HOME, for both copy and symlink
# modes, across all three runtimes at once.
for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment all --features shortcuts \
    --mode "$mode" --on-exist skip --yes >/dev/null

  cc_nr="$test_home/.claude/commands/nr.md"
  cc_av="$test_home/.claude/commands/av.md"
  oc_nr="$test_home/.config/opencode/commands/nr.md"
  oc_av="$test_home/.config/opencode/commands/av.md"
  codex_nr="$test_home/.agents/skills/nr"
  codex_av="$test_home/.agents/skills/av"

  test -f "$cc_nr"
  test -f "$cc_av"
  test -f "$oc_nr"
  test -f "$oc_av"
  test -f "$codex_nr/SKILL.md"
  test -f "$codex_av/SKILL.md"

  # Claude Code and OpenCode commands are the payload files verbatim.
  cmp "$KIT_DIR/shared/shortcuts/nr.md" "$cc_nr"
  cmp "$KIT_DIR/shared/shortcuts/nr.md" "$oc_nr"
  cmp "$KIT_DIR/shared/shortcuts/av.md" "$cc_av"
  cmp "$KIT_DIR/shared/shortcuts/av.md" "$oc_av"

  # The installed Codex skill is the right one, not a copy-paste of the other.
  grep -q '^name: nr$' "$codex_nr/SKILL.md"
  grep -q '^name: av$' "$codex_av/SKILL.md"

  if [[ "$mode" == copy ]]; then
    test ! -L "$cc_nr"
    test ! -L "$cc_av"
    test ! -L "$oc_nr"
    test ! -L "$oc_av"
    test -d "$codex_nr"
    test ! -L "$codex_nr"
    test ! -L "$codex_nr/SKILL.md"
    test -d "$codex_av"
    test ! -L "$codex_av"
    test ! -L "$codex_av/SKILL.md"
  else
    test -L "$cc_nr"
    test "$(readlink "$cc_nr")" = "$KIT_DIR/shared/shortcuts/nr.md"
    test -L "$cc_av"
    test "$(readlink "$cc_av")" = "$KIT_DIR/shared/shortcuts/av.md"
    test -L "$oc_nr"
    test "$(readlink "$oc_nr")" = "$KIT_DIR/shared/shortcuts/nr.md"
    test -L "$oc_av"
    test "$(readlink "$oc_av")" = "$KIT_DIR/shared/shortcuts/av.md"
    test -L "$codex_nr"
    test "$(readlink "$codex_nr")" = "$KIT_DIR/codex/skills/nr"
    test -L "$codex_av"
    test "$(readlink "$codex_av")" = "$KIT_DIR/codex/skills/av"
  fi

  HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
  test ! -e "$cc_nr";    test ! -L "$cc_nr"
  test ! -e "$cc_av";    test ! -L "$cc_av"
  test ! -e "$oc_nr";    test ! -L "$oc_nr"
  test ! -e "$oc_av";    test ! -L "$oc_av"
  test ! -e "$codex_nr"; test ! -L "$codex_nr"
  test ! -e "$codex_av"; test ! -L "$codex_av"
done

echo "shortcuts install/uninstall across Claude Code, OpenCode, Codex: PASS"

# Features outside shortcuts never pull nr/av in as a side effect — in
# particular, doc-harness's shared/commands/ sweep (install.sh:279,288) must
# never pick these up, since their source lives outside that swept directory.
non_shortcuts_home="$TEST_ROOT/non-shortcuts-home"
mkdir -p "$non_shortcuts_home"
HOME="$non_shortcuts_home" "$KIT_DIR/install.sh" \
  --environment all --features doc-harness \
  --mode symlink --on-exist skip --yes >/dev/null
test ! -e "$non_shortcuts_home/.claude/commands/nr.md"
test ! -e "$non_shortcuts_home/.claude/commands/av.md"
test ! -e "$non_shortcuts_home/.config/opencode/commands/nr.md"
test ! -e "$non_shortcuts_home/.config/opencode/commands/av.md"
test ! -e "$non_shortcuts_home/.agents/skills/nr"
test ! -e "$non_shortcuts_home/.agents/skills/av"
echo "shortcuts excluded from doc-harness sweep: PASS"

# Regression: combining doc-harness (which sweeps shared/commands/ wholesale
# into Claude Code at install.sh:279 and OpenCode at :288) with shortcuts must
# never produce a duplicate destination for nr/av — a duplicate would make
# --on-exist backup move the file the first pass just installed to .bak.
combo_home="$TEST_ROOT/combo-home"
mkdir -p "$combo_home"
HOME="$combo_home" "$KIT_DIR/install.sh" \
  --environment both --features doc-harness,shortcuts \
  --mode symlink --on-exist backup --yes >/dev/null
test -f "$combo_home/.claude/commands/nr.md"
test -f "$combo_home/.claude/commands/av.md"
test -f "$combo_home/.config/opencode/commands/nr.md"
test -f "$combo_home/.config/opencode/commands/av.md"
test ! -e "$combo_home/.claude/commands/nr.md.bak"
test ! -e "$combo_home/.claude/commands/av.md.bak"
test ! -e "$combo_home/.config/opencode/commands/nr.md.bak"
test ! -e "$combo_home/.config/opencode/commands/av.md.bak"
manifest="$combo_home/.config/mrcall-ai-kit/installed.tsv"
count="$(awk -F '\t' -v dest="$combo_home/.claude/commands/nr.md" \
  '$3 == dest { count++ } END { print count + 0 }' "$manifest")"
[[ "$count" -eq 1 ]] || {
  echo "expected one nr.md manifest entry, got $count" >&2
  exit 1
}
echo "shortcuts + doc-harness combined install has no duplicate destination: PASS"

# Every case above selects more than one runtime, so none of them can catch a
# per-runtime gate that stopped gating. Install into one runtime at a time and
# require the other two to receive nothing.
single_runtime() { # $1=environment  $2..=paths that must NOT exist
  local environment="$1"; shift
  local home="$TEST_ROOT/only-$environment"
  mkdir -p "$home"
  HOME="$home" "$KIT_DIR/install.sh" \
    --environment "$environment" --features shortcuts \
    --mode symlink --on-exist skip --yes >/dev/null
  local leaked
  for leaked in "$@"; do
    [[ ! -e "$home/$leaked" && ! -L "$home/$leaked" ]] || {
      echo "--environment $environment leaked $leaked" >&2
      exit 1
    }
  done
}

single_runtime claude \
  .config/opencode/commands/nr.md .config/opencode/commands/av.md \
  .agents/skills/nr .agents/skills/av
test -f "$TEST_ROOT/only-claude/.claude/commands/nr.md"

single_runtime opencode \
  .claude/commands/nr.md .claude/commands/av.md \
  .agents/skills/nr .agents/skills/av
test -f "$TEST_ROOT/only-opencode/.config/opencode/commands/nr.md"

single_runtime codex \
  .claude/commands/nr.md .claude/commands/av.md \
  .config/opencode/commands/nr.md .config/opencode/commands/av.md
test -f "$TEST_ROOT/only-codex/.agents/skills/nr/SKILL.md"

echo "shortcuts reach only the selected runtime: PASS"
