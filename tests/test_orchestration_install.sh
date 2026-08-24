#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# The orchestrator agent and skill read ~/.config/opencode/llms.md at startup and
# at every worker pick, so a clean orchestration install must put it there.
for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment opencode --features orchestration \
    --mode "$mode" --on-exist skip --yes >/dev/null

  llms="$test_home/.config/opencode/llms.md"
  test -f "$llms"
  test -f "$test_home/.config/opencode/agents/orchestrator.md"
  test -f "$test_home/.config/opencode/skills/orchestrator/SKILL.md"
  if [[ "$mode" == copy ]]; then
    test ! -L "$llms"
  else
    test -L "$llms"
  fi
  # Every path the shipped orchestrator is told to read must now resolve.
  grep -q 'Orchestrator Models' "$llms"
done
echo "orchestration install ships llms.md: PASS"

# ── idempotent: a second install with --on-exist skip adds no duplicate ────
test_home="$TEST_ROOT/idempotent"
mkdir -p "$test_home"
for _ in 1 2; do
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment opencode --features orchestration \
    --mode symlink --on-exist skip --yes >/dev/null
done
manifest="$test_home/.config/mrcall-ai-kit/installed.tsv"
count=$(grep -c 'opencode/llms\.md' "$manifest")
[[ "$count" -eq 1 ]] || { echo "expected exactly one llms.md manifest entry, got $count" >&2; exit 1; }
echo "orchestration install is idempotent for llms.md: PASS"

# ── llms.md belongs to orchestration: workers alone must not pull it in ────
test_home="$TEST_ROOT/workers-only"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment opencode --features workers \
  --mode symlink --on-exist skip --yes >/dev/null
test ! -e "$test_home/.config/opencode/llms.md"
echo "llms.md not installed without orchestration: PASS"

# ── orchestration is OpenCode-only: dropped when OpenCode isn't selected ───
test_home="$TEST_ROOT/claude-only"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment claude --features orchestration \
  --mode symlink --on-exist skip --yes >/dev/null 2>&1 || true
test ! -e "$test_home/.config/opencode/llms.md"
echo "orchestration feature dropped without OpenCode: PASS"

# ── uninstall removes llms.md through the manifest, no special case ────────
for mode in copy symlink; do
  test_home="$TEST_ROOT/uninstall-$mode"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment opencode --features orchestration \
    --mode "$mode" --on-exist skip --yes >/dev/null
  test -e "$test_home/.config/opencode/llms.md"
  HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
  test ! -e "$test_home/.config/opencode/llms.md"
  test ! -L "$test_home/.config/opencode/llms.md"
  test ! -e "$test_home/.config/opencode/skills/orchestrator"
done
echo "orchestration uninstall removes llms.md: PASS"
