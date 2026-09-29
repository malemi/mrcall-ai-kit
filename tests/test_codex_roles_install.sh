#!/usr/bin/env bash
set -euo pipefail
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode"
  mkdir -p "$test_home/.codex/agents"
  printf 'Foreign global rule.\n' > "$test_home/.codex/AGENTS.md"
  printf 'name = "foreign"\ndescription = "keep"\ndeveloper_instructions = "keep"\n' > "$test_home/.codex/agents/foreign.toml"
  HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
    --mode "$mode" --on-exist skip --yes > "$TEST_ROOT/$mode.out"
  for role in execute plan reviewer verify; do
    file="$test_home/.codex/agents/$role.toml"
    test -f "$file"
    cmp "$file" "$KIT_DIR/codex/agents/$role.toml"
    test ! -L "$file"
  done
  grep -q 'Foreign global rule.' "$test_home/.codex/AGENTS.md"
  test "$(grep -c 'mrcall-ai-kit:codex-agents:start' "$test_home/.codex/AGENTS.md")" -eq 1
  HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
    --mode "$mode" --on-exist skip --yes > /dev/null
  test "$(grep -c 'mrcall-ai-kit:codex-agents:start' "$test_home/.codex/AGENTS.md")" -eq 1
  HOME="$test_home" python3 "$test_home/.config/mrcall-ai-kit/ai-budget.py" \
    > "$TEST_ROOT/$mode.budget"
  grep -q 'Codex: execute, plan, reviewer, verify inherit the session model' "$TEST_ROOT/$mode.budget"
  HOME="$test_home" bash "$test_home/.config/mrcall-ai-kit/ai-help.sh" \
    > "$TEST_ROOT/$mode.help"
  grep -q '| reviewer | inherits session model |' "$TEST_ROOT/$mode.help"
  HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes > /dev/null
  for role in execute plan reviewer verify; do test ! -e "$test_home/.codex/agents/$role.toml"; done
  test -f "$test_home/.codex/agents/foreign.toml"
  test "$(cat "$test_home/.codex/AGENTS.md")" = 'Foreign global rule.'
done

test_home="$TEST_ROOT/foreign-reviewer"
mkdir -p "$test_home/.codex/agents"
printf 'name = "reviewer"\ndescription = "mine"\ndeveloper_instructions = "mine"\n' \
  > "$test_home/.codex/agents/reviewer.toml"
if HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist skip --yes > "$TEST_ROOT/conflict.out" 2>&1; then
  echo 'foreign reviewer conflict was silently accepted' >&2; exit 1
fi
grep -q 'Codex role conflict:' "$TEST_ROOT/conflict.out"
test ! -e "$test_home/.codex/AGENTS.md"
grep -q 'description = "mine"' "$test_home/.codex/agents/reviewer.toml"

test_home="$TEST_ROOT/edited-reviewer"
mkdir -p "$test_home/.codex/agents"
printf 'name = "reviewer"\ndescription = "original"\ndeveloper_instructions = "original"\n' \
  > "$test_home/.codex/agents/reviewer.toml"
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist backup --yes > /dev/null
printf 'name = "reviewer"\ndescription = "operator edit"\ndeveloper_instructions = "operator edit"\n' \
  > "$test_home/.codex/agents/reviewer.toml"
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist backup --yes > /dev/null
grep -q 'description = "original"' "$test_home/.codex/agents/reviewer.toml.bak"
grep -q 'description = "operator edit"' "$test_home/.codex/agents/reviewer.toml.bak.1"
cmp "$test_home/.codex/agents/reviewer.toml" "$KIT_DIR/codex/agents/reviewer.toml"
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes --restore-backups > /dev/null
grep -q 'description = "operator edit"' "$test_home/.codex/agents/reviewer.toml"
grep -q 'description = "original"' "$test_home/.codex/agents/reviewer.toml.bak"

test_home="$TEST_ROOT/symlinked-reviewer"
mkdir -p "$test_home/.codex/agents"
ln -s "$KIT_DIR/codex/agents/reviewer.toml" "$test_home/.codex/agents/reviewer.toml"
if HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode symlink --on-exist skip --yes > "$TEST_ROOT/symlink-conflict.out" 2>&1; then
  echo 'symlinked reviewer profile was silently accepted' >&2; exit 1
fi
grep -q 'Codex role conflict:.*is symlinked' "$TEST_ROOT/symlink-conflict.out"
test ! -e "$test_home/.codex/AGENTS.md"
test -L "$test_home/.codex/agents/reviewer.toml"

test_home="$TEST_ROOT/foreign-reviewer"
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist backup --yes > /dev/null
cmp "$test_home/.codex/agents/reviewer.toml.bak" \
  <(printf 'name = "reviewer"\ndescription = "mine"\ndeveloper_instructions = "mine"\n')
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist backup --yes > /dev/null
grep -q 'description = "mine"' "$test_home/.codex/agents/reviewer.toml.bak"
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes --restore-backups > /dev/null
grep -q 'description = "mine"' "$test_home/.codex/agents/reviewer.toml"

echo 'Codex role install, discovery, budget report, and uninstall: PASS'
