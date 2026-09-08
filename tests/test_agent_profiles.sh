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
grep -q 'never delegate a trivial local edit' "$template" \
  || fail "template lost the trivial-delegation guard"

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
# The sentinel is load-bearing: `$( )` strips trailing newlines, so a hook that
# fell through to a bare `print()` would emit one blank line and still look
# empty here. Appending a dot makes the difference visible.
hook_out="$(printf '{"session_id":"tiny","cwd":"/nonexistent","transcript_path":"/tmp/tiny.jsonl"}' \
  | HOME="$router_home" python3 "$KIT_DIR/claude/scripts/router-hook.py"; printf .)"
[[ "$hook_out" == "." ]] \
  || fail "router reprints standing instructions the session already holds"
echo "router's real hook output carries no standing directive: PASS"

# Those guarantees are not gone: their carrier is the managed template, which
# every managed repository installs as its own CLAUDE.md and every session
# therefore already holds. Each assertion below fails if the rule leaves it.
grep -q 'Implement directly when fastest' "$template" \
  || fail "template does not keep narrow work local"
grep -q 'coordination, waiting, and review' "$template" \
  || fail "template lacks positive-value delegation gate"
grep -q 'Use the fast path only when every' "$template" \
  || fail "template lacks strict fast-path criteria"
grep -q 'Do not plan until it returns' "$template" \
  || fail "template can plan before brief approval"
grep -q 'Do not delegate or implement until it' "$template" \
  || fail "template can delegate or implement before plan approval"
grep -q 'separate final end-to-end review' "$template" \
  || fail "template lacks separate final review"
grep -q 'A review returns exactly one of' "$template" \
  || fail "template lacks bounded review verdicts"
# The eighth guarantee — that nothing tells the session to delegate ordinary
# work by default — is asserted positively at the top of this file, where the
# template must still say `never delegate a trivial local edit`. Asserting the
# absence of the hook's old phrasing here would be a test that cannot fail.
echo "the managed template carries what the router stopped reprinting: PASS"

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
