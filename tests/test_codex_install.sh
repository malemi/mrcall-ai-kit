#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

for command in doc-create doc-start doc-end; do
  cmp "$KIT_DIR/shared/commands/$command.md" \
      "$KIT_DIR/codex/skills/$command/WORKFLOW.md"
done

for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment codex --features doc-harness \
    --mode "$mode" --on-exist skip --yes >/dev/null

  for command in doc-create doc-start doc-end; do
    skill="$test_home/.agents/skills/$command"
    test -f "$skill/SKILL.md"
    test -f "$skill/WORKFLOW.md"
    if [[ "$mode" == copy ]]; then
      test -d "$skill"
      test ! -L "$skill/SKILL.md"
      test ! -L "$skill/WORKFLOW.md"
    else
      test -L "$skill"
    fi
  done
  test ! -e "$test_home/.codex/prompts"
done

echo "Codex install discovery layout: PASS"
