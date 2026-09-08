#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

for command in doc-create doc-start doc-end; do
  cmp "$KIT_DIR/shared/commands/$command.md" \
      "$KIT_DIR/codex/skills/$command/WORKFLOW.md"
done

# The managed template is one kit-global artifact shared by every runtime. A
# repeated install for an already-covered runtime must not add another manifest
# entry, and uninstall must remove both copy and symlink installs.
for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  for environment in claude codex opencode claude; do
    HOME="$test_home" "$KIT_DIR/install.sh" \
      --environment "$environment" --features doc-harness \
      --mode "$mode" --on-exist skip --yes >/dev/null
  done

  template="$test_home/.config/mrcall-ai-kit/CLAUDE.template.md"
  checker="$test_home/.config/mrcall-ai-kit/doc-check.py"
  manifest="$test_home/.config/mrcall-ai-kit/installed.tsv"
  test -f "$template"
  test -f "$checker"
  # /ai-help calls this from the kit-global home; without it the command is dead.
  test -f "$test_home/.config/mrcall-ai-kit/ai-help.sh"
  cmp "$KIT_DIR/shared/templates/CLAUDE.md" "$template"
  count="$(awk -F '\t' -v dest="$template" \
    '$3 == dest { count++ } END { print count + 0 }' "$manifest")"
  [[ "$count" -eq 1 ]] || {
    echo "expected one managed-template manifest entry, got $count" >&2
    exit 1
  }
  if [[ "$mode" == copy ]]; then
    test ! -L "$template"
    test ! -L "$checker"
  else
    test -L "$template"
    test -L "$checker"
    test "$(readlink "$template")" = "$KIT_DIR/shared/templates/CLAUDE.md"
  fi

  test -f "$test_home/.claude/commands/doc-create.md"
  test -f "$test_home/.config/opencode/commands/doc-create.md"

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

  HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
  test ! -e "$template"
  test ! -L "$template"
  test ! -e "$checker"
  test ! -L "$checker"
  test ! -e "$test_home/.claude/commands/doc-create.md"
  test ! -e "$test_home/.agents/skills/doc-create"
  test ! -L "$test_home/.agents/skills/doc-create"
  test ! -e "$test_home/.config/opencode/commands/doc-create.md"
done

echo "doc-harness template propagation and Codex discovery layout: PASS"

# Features outside doc-harness never pull in either global documentation asset.
non_doc_home="$TEST_ROOT/non-doc-home"
mkdir -p "$non_doc_home"
HOME="$non_doc_home" "$KIT_DIR/install.sh" \
  --environment opencode --features workers \
  --mode symlink --on-exist skip --yes >/dev/null
test ! -e "$non_doc_home/.config/mrcall-ai-kit/CLAUDE.template.md"
test ! -L "$non_doc_home/.config/mrcall-ai-kit/CLAUDE.template.md"
test ! -e "$non_doc_home/.config/mrcall-ai-kit/doc-check.py"
test ! -L "$non_doc_home/.config/mrcall-ai-kit/doc-check.py"
echo "managed template excluded without doc-harness: PASS"

# A missing required source must stop during plan construction. In particular,
# symlink mode must never record a dangling link as a successful installation.
missing_kit="$TEST_ROOT/missing-kit"
mkdir -p "$missing_kit/shared/scripts"
cp "$KIT_DIR/install.sh" "$missing_kit/install.sh"
cp "$KIT_DIR/shared/scripts/doc-check.py" "$missing_kit/shared/scripts/doc-check.py"
missing_home="$TEST_ROOT/missing-home"
mkdir -p "$missing_home"
if output="$(HOME="$missing_home" "$missing_kit/install.sh" \
  --environment codex --features doc-harness \
  --mode symlink --on-exist skip --yes 2>&1)"; then
  echo "expected a missing managed-template source to fail" >&2
  exit 1
fi
[[ "$output" == *"Missing install source: $missing_kit/shared/templates/CLAUDE.md"* ]]
test ! -e "$missing_home/.config/mrcall-ai-kit"
echo "missing required install source fails before writes: PASS"
