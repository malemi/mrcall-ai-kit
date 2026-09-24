#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT
RETIRED="$KIT_DIR/shared/roles/retired.txt"

# No file the kit has retired may come back with an install. Their names live in
# retired.txt alone, so the assertion reads them from there.
none_retired() { # $1 = test home
  local src dest
  while IFS=$'\t' read -r src dest; do
    [[ -z "$src" || "$src" == \#* ]] && continue
    if [[ -e "$1/$dest" ]]; then echo "install shipped a retired file: $dest" >&2; exit 1; fi
  done < "$RETIRED"
}

for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment opencode --features orchestration \
    --mode "$mode" --on-exist skip --yes >/dev/null

  agent="$test_home/.config/opencode/agents/orchestrator.md"
  test -f "$agent"
  test -f "$test_home/.config/opencode/skills/orchestrator/SKILL.md"
  if [[ "$mode" == copy ]]; then test ! -L "$agent"; else test -L "$agent"; fi
  # The leads may delegate to the roles, and to no model-named agent.
  grep -q 'execute: allow' "$test_home/.config/opencode/agents/build.md"
  grep -q 'verify: allow' "$test_home/.config/opencode/agents/orchestrator.md"
  none_retired "$test_home"
done
echo "orchestration install ships the leads and no retired file: PASS"

# ── idempotent: a second install with --on-exist skip adds no duplicate ────
test_home="$TEST_ROOT/idempotent"
mkdir -p "$test_home"
for _ in 1 2; do
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment opencode --features orchestration \
    --mode symlink --on-exist skip --yes >/dev/null
done
manifest="$test_home/.config/mrcall-ai-kit/installed.tsv"
count=$(grep -c 'opencode/agents/orchestrator\.md' "$manifest")
[[ "$count" -eq 1 ]] || { echo "expected exactly one orchestrator.md manifest entry, got $count" >&2; exit 1; }
echo "orchestration install is idempotent: PASS"

# ── the role agents belong to workers: orchestration alone does not ship them ─
test ! -e "$TEST_ROOT/idempotent/.config/opencode/agents/execute.md"
test_home="$TEST_ROOT/workers-only"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment opencode --features workers \
  --mode symlink --on-exist skip --yes >/dev/null
test -f "$test_home/.config/opencode/agents/execute.md"
test -f "$test_home/.config/opencode/agents/verify.md"
test ! -e "$test_home/.config/opencode/agents/orchestrator.md"
none_retired "$test_home"
echo "workers installs the roles, and only the roles: PASS"

# ── orchestration is OpenCode-only: dropped when OpenCode isn't selected ───
test_home="$TEST_ROOT/claude-only"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment claude --features orchestration \
  --mode symlink --on-exist skip --yes >/dev/null 2>&1 || true
test ! -e "$test_home/.config/opencode/agents/orchestrator.md"
echo "orchestration feature dropped without OpenCode: PASS"

# ── uninstall removes the orchestration install through the manifest ──────
for mode in copy symlink; do
  test_home="$TEST_ROOT/uninstall-$mode"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment opencode --features orchestration \
    --mode "$mode" --on-exist skip --yes >/dev/null
  test -e "$test_home/.config/opencode/agents/orchestrator.md"
  HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
  test ! -e "$test_home/.config/opencode/agents/orchestrator.md"
  test ! -L "$test_home/.config/opencode/agents/orchestrator.md"
  test ! -e "$test_home/.config/opencode/skills/orchestrator"
done
echo "orchestration uninstall removes what it installed: PASS"
