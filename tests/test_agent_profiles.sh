#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() { echo "$1" >&2; exit 1; }

workers=("$KIT_DIR"/claude/agents/worker-*.md "$KIT_DIR"/opencode/agents/worker-*.md)
[[ "${#workers[@]}" -eq 19 ]] || fail "expected 19 worker profiles, got ${#workers[@]}"
for worker in "${workers[@]}"; do
  grep -q '^## Proportional execution$' "$worker" || fail "missing proportional contract: $worker"
  grep -q 'smallest real check that could fail because of your change' "$worker" \
    || fail "missing focused verification rule: $worker"
  grep -q 'do not expand it into unrelated research' "$worker" \
    || fail "missing scope budget: $worker"
done
echo "all worker profiles carry the proportional-execution contract: PASS"

primary="$KIT_DIR/opencode/agents/orchestrator.md"
skill="$KIT_DIR/opencode/skills/orchestrator/SKILL.md"
template="$KIT_DIR/shared/templates/CLAUDE.md"
grep -q "CTO" "$primary"
grep -q "CTO" "$skill"
grep -q "CTO" "$template"
grep -q 'Never delegate a trivial local edit' "$primary"
grep -q 'Do not delegate a trivial local edit' "$skill"
grep -q 'never delegate a trivial local edit' "$template"

for banned in \
  'FIRST action must be to call the `question` tool' \
  'Default: NEVER write code' \
  'Everything else: delegate' \
  'ASK — Model Selection' \
  'ASK — Strategy' \
  'ASK — Task Decomposition'; do
  if grep -Fq "$banned" "$primary" "$skill"; then
    fail "mandatory ceremony remains: $banned"
  fi
done
echo "primary profiles require autonomy and contain no mandatory approval ceremony: PASS"

router_home="$TEST_ROOT/router-home"
mkdir -p "$router_home/.config/mrcall-ai-kit"
touch "$router_home/.config/mrcall-ai-kit/router.on"
directive="$(printf '{"session_id":"tiny","cwd":"/nonexistent","transcript_path":"/tmp/tiny.jsonl"}' \
  | HOME="$router_home" python3 "$KIT_DIR/claude/scripts/router-hook.py")"
[[ "$directive" == *"narrow local implementation or lookup -> do it directly"* ]] \
  || fail "router does not keep narrow work local"
[[ "$directive" == *"Delegate only when the benefit exceeds prompting, waiting, and review"* ]] \
  || fail "router lacks positive-value delegation gate"
[[ "$directive" != *"normal implementation or lookup work -> delegate"* ]] \
  || fail "router still delegates normal work by default"
echo "router's real hook output keeps narrow work local: PASS"

for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment all --features doc-harness,orchestration,workers,router \
    --mode "$mode" --on-exist skip --yes >/dev/null
  grep -q 'human CTO' "$test_home/.config/mrcall-ai-kit/CLAUDE.template.md"
  grep -q 'Never delegate a trivial local edit' "$test_home/.config/opencode/agents/orchestrator.md"
  grep -q '^## Proportional execution$' "$test_home/.claude/agents/worker-sonnet.md"
  grep -q '^## Proportional execution$' "$test_home/.config/opencode/agents/worker-sonnet.md"
done
echo "copy and symlink installs ship the new primary and worker contracts: PASS"
