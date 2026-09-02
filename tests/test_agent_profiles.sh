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
build="$KIT_DIR/opencode/agents/build.md"
planner="$KIT_DIR/opencode/agents/plan.md"
reviewer="$KIT_DIR/opencode/agents/reviewer.md"
command="$KIT_DIR/opencode/commands/orchestrator.md"
skill="$KIT_DIR/opencode/skills/orchestrator/SKILL.md"
architecture="$KIT_DIR/opencode/skills/orchestrator/ARCHITECTURE.md"
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

for lead in "$primary" "$build" "$skill"; do
  grep -q 'Use the fast path only when every condition holds\|direct fast path only when every condition holds\|Use the direct fast path only when every condition holds' "$lead" \
    || fail "missing strict fast-path gate: $lead"
  grep -q 'Do not write the execution plan until\|before writing the milestone plan\|before planning begins' "$lead" \
    || fail "missing brief-before-plan gate: $lead"
  grep -q 'separate final' "$lead" || fail "missing separate final review: $lead"
done
grep -A10 '^  task:' "$build" | grep -q 'reviewer: allow' \
  || fail "build cannot invoke reviewer"
grep -A6 '^  task:' "$planner" | grep -q 'reviewer: allow' \
  || fail "plan cannot invoke reviewer"
grep -q 'edit: deny' "$planner" && grep -q 'bash: deny' "$planner" \
  || fail "plan mode is not read-only"
grep -q 'Do not draft the plan until' "$planner" \
  || fail "plan mode can bypass brief review"
grep -q 'Never write the artifacts or begin implementation' "$planner" \
  || fail "plan mode lacks non-executing handoff"
for verdict in APPROVED REVISE FAST_PATH BLOCKED; do
  grep -q "\`$verdict\`" "$reviewer" || fail "reviewer lacks $verdict verdict"
done
for kind in brief plan milestone final; do
  grep -q "\`$kind\`" "$reviewer" || fail "reviewer lacks $kind review kind"
done
grep -q 'internal engineering gates, never CTO approval prompts' "$reviewer" \
  || fail "reviewer turns gates into CTO approval"
grep -q 'brief, plan, milestone, and separate final review gates' "$command" \
  || fail "orchestrator command omits reviewed lifecycle"
grep -q 'brief -> fresh review -> APPROVED' "$architecture" \
  || fail "architecture omits brief review transition"
echo "OpenCode primaries and reviewer enforce the reviewed delivery lifecycle: PASS"

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
[[ "$directive" == *"Use the direct fast path only when every condition holds"* ]] \
  || fail "router lacks strict fast-path criteria"
[[ "$directive" == *"Do not plan until its verdict is APPROVED"* ]] \
  || fail "router can plan before brief approval"
[[ "$directive" == *"Do not delegate or begin implementation until its verdict is APPROVED"* ]] \
  || fail "router can implement before plan approval"
[[ "$directive" == *"separate final end-to-end review"* ]] \
  || fail "router lacks separate final review"
[[ "$directive" == *"APPROVED, REVISE, FAST_PATH, or BLOCKED"* ]] \
  || fail "router lacks bounded review verdicts"
echo "router's real hook output keeps narrow work local: PASS"

for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment all --features doc-harness,orchestration,workers,router \
    --mode "$mode" --on-exist skip --yes >/dev/null
  grep -q 'human CTO' "$test_home/.config/mrcall-ai-kit/CLAUDE.template.md"
  grep -q 'Never delegate a trivial local edit' "$test_home/.config/opencode/agents/orchestrator.md"
  grep -q 'reviewer: allow' "$test_home/.config/opencode/agents/build.md"
  grep -q 'Do not draft the plan until' "$test_home/.config/opencode/agents/plan.md"
  grep -q 'Return exactly one verdict' "$test_home/.config/opencode/agents/reviewer.md"
  grep -q '^## Artifact and integration review$' "$test_home/.claude/agents/worker-opus.md"
  grep -q 'Review tasks are read-only' "$test_home/.claude/agents/worker-opus.md"
  grep -q 'APPROVED | REVISE | FAST_PATH' "$test_home/.claude/agents/worker-opus.md"
  grep -q '^## Proportional execution$' "$test_home/.claude/agents/worker-sonnet.md"
  grep -q '^## Proportional execution$' "$test_home/.config/opencode/agents/worker-sonnet.md"
done
echo "copy and symlink installs ship the new primary and worker contracts: PASS"
