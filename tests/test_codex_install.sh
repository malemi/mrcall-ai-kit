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

  template="$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
  checker="$test_home/.config/mrcall-ai-kit/doc-check.py"
  keywords="$test_home/.config/mrcall-ai-kit/doc-keywords.py"
  manifest="$test_home/.config/mrcall-ai-kit/installed.tsv"
  test -f "$template"
  test -f "$checker"
  test -f "$test_home/.config/mrcall-ai-kit/doc-evidence.py"
  test -f "$keywords"
  test -f "$test_home/.config/mrcall-ai-kit/doc-migrate.py"
  test -f "$test_home/.config/mrcall-ai-kit/doc-compat.py"
  diff -qr "$KIT_DIR/shared/templates/legacy" "$test_home/.config/mrcall-ai-kit/legacy"
  python3 "$test_home/.config/mrcall-ai-kit/doc-migrate.py" --help > /dev/null
  python3 "$test_home/.config/mrcall-ai-kit/doc-compat.py" --help > /dev/null
  test ! -e "$test_home/.config/mrcall-ai-kit/CLAUDE.template.md"
  (cd "$test_home" && python3 "$keywords" --repo "$KIT_DIR" --json >/dev/null)
  # /ai-help calls this from the kit-global home; without it the command is dead.
  test -f "$test_home/.config/mrcall-ai-kit/ai-help.sh"
  cmp "$KIT_DIR/shared/templates/AGENTS.block.md" "$template"
  count="$(awk -F '\t' -v dest="$template" \
    '$3 == dest { count++ } END { print count + 0 }' "$manifest")"
  [[ "$count" -eq 1 ]] || {
    echo "expected one managed-template manifest entry, got $count" >&2
    exit 1
  }
  count="$(awk -F '\t' -v dest="$keywords" \
    '$3 == dest { count++ } END { print count + 0 }' "$manifest")"
  [[ "$count" -eq 1 ]] || {
    echo "expected one keyword-checker manifest entry, got $count" >&2
    exit 1
  }
  if [[ "$mode" == copy ]]; then
    test ! -L "$template"
    test ! -L "$checker"
    test ! -L "$keywords"
  else
    test -L "$template"
    test -L "$checker"
    test -L "$keywords"
    test "$(readlink "$template")" = "$KIT_DIR/shared/templates/AGENTS.block.md"
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
  test ! -e "$keywords"
  test ! -L "$keywords"
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
test ! -e "$non_doc_home/.config/mrcall-ai-kit/AGENTS.block.md"
test ! -L "$non_doc_home/.config/mrcall-ai-kit/AGENTS.block.md"
test ! -e "$non_doc_home/.config/mrcall-ai-kit/doc-check.py"
test ! -L "$non_doc_home/.config/mrcall-ai-kit/doc-check.py"
test ! -e "$non_doc_home/.config/mrcall-ai-kit/doc-keywords.py"
test ! -L "$non_doc_home/.config/mrcall-ai-kit/doc-keywords.py"
echo "managed template excluded without doc-harness: PASS"

# A missing required source must stop during plan construction. In particular,
# symlink mode must never record a dangling link as a successful installation.
missing_kit="$TEST_ROOT/missing-kit"
mkdir -p "$missing_kit/shared/scripts"
cp "$KIT_DIR/install.sh" "$missing_kit/install.sh"
cp "$KIT_DIR/shared/scripts/doc-check.py" "$missing_kit/shared/scripts/doc-check.py"
cp "$KIT_DIR/shared/scripts/doc-evidence.py" "$missing_kit/shared/scripts/doc-evidence.py"
cp "$KIT_DIR/shared/scripts/doc-keywords.py" "$missing_kit/shared/scripts/doc-keywords.py"
cp "$KIT_DIR/shared/scripts/doc-compat.py" "$missing_kit/shared/scripts/doc-compat.py"
cp "$KIT_DIR/shared/scripts/doc-migrate.py" "$missing_kit/shared/scripts/doc-migrate.py"
missing_home="$TEST_ROOT/missing-home"
mkdir -p "$missing_home"
if output="$(HOME="$missing_home" "$missing_kit/install.sh" \
  --environment codex --features doc-harness \
  --mode symlink --on-exist skip --yes 2>&1)"; then
  echo "expected a missing managed-template source to fail" >&2
  exit 1
fi
[[ "$output" == *"Missing install source: $missing_kit/shared/templates/AGENTS.block.md"* ]]
test ! -e "$missing_home/.config/mrcall-ai-kit"
echo "missing required install source fails before writes: PASS"

for mode in copy symlink; do
  for ownership in known foreign; do
    test_home="$TEST_ROOT/retire-$mode-$ownership"
    mkdir -p "$test_home/.config/mrcall-ai-kit"
    old="$test_home/.config/mrcall-ai-kit/CLAUDE.template.md"
    if [[ "$ownership" == known ]]; then
      if [[ "$mode" == copy ]]; then
        cp "$KIT_DIR/shared/templates/legacy/v8/CLAUDE.md" "$old"
      else
        ln -s "$KIT_DIR/shared/templates/legacy/v8/CLAUDE.md" "$old"
      fi
    else
      printf 'Foreign template contents.\n' > "$old"
    fi
    cp -L "$old" "$TEST_ROOT/before"
    HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
      --mode "$mode" --on-exist backup --yes --dry-run > /dev/null
    cmp "$old" "$TEST_ROOT/before"
    test ! -e "$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
    HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
      --mode "$mode" --on-exist backup --yes > /dev/null
    if [[ "$ownership" == known ]]; then
      test ! -e "$old"
      test ! -L "$old"
      cmp "$old.bak" "$TEST_ROOT/before"
    else
      cmp "$old" "$TEST_ROOT/before"
    fi
    HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes --restore-backups > /dev/null
    cmp "$old" "$TEST_ROOT/before"
  done
done

test_home="$TEST_ROOT/foreign-copies"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist skip --yes > /dev/null
printf 'Foreign change.\n' >> "$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
printf 'Foreign skill.\n' >> "$test_home/.agents/skills/doc-start/SKILL.md"
cp "$test_home/.config/mrcall-ai-kit/AGENTS.block.md" "$TEST_ROOT/foreign-block"
cp "$test_home/.agents/skills/doc-start/SKILL.md" "$TEST_ROOT/foreign-skill"
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes > /dev/null
cmp "$test_home/.config/mrcall-ai-kit/AGENTS.block.md" "$TEST_ROOT/foreign-block"
cmp "$test_home/.agents/skills/doc-start/SKILL.md" "$TEST_ROOT/foreign-skill"

test_home="$TEST_ROOT/foreign-link"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode symlink --on-exist skip --yes > /dev/null
rm "$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
printf 'Foreign target.\n' > "$TEST_ROOT/foreign-target"
ln -s "$TEST_ROOT/foreign-target" "$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes > /dev/null
test "$(readlink "$test_home/.config/mrcall-ai-kit/AGENTS.block.md")" = "$TEST_ROOT/foreign-target"
echo 'v9 asset retirement, dry-run, backup restoration, and foreign preservation: PASS'

snapshot="$TEST_ROOT/copy-source"
mkdir -p "$snapshot"
cp -r "$KIT_DIR/shared" "$KIT_DIR/claude" "$KIT_DIR/opencode" "$KIT_DIR/codex" "$KIT_DIR/install.sh" "$KIT_DIR/uninstall.sh" "$snapshot/"
test_home="$TEST_ROOT/source-gone"
mkdir -p "$test_home"
HOME="$test_home" "$snapshot/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist skip --yes > /dev/null
cp "$snapshot/uninstall.sh" "$TEST_ROOT/standalone-uninstall.sh"
mv "$snapshot" "$snapshot-moved"
HOME="$test_home" "$TEST_ROOT/standalone-uninstall.sh" --yes > /dev/null
test ! -e "$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
test ! -e "$test_home/.agents/skills/doc-start"
test ! -e "$test_home/.codex/AGENTS.md"
test ! -e "$test_home/.codex/agents/reviewer.toml"

test_home="$TEST_ROOT/legacy-log"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" --environment codex --features doc-harness \
  --mode copy --on-exist skip --yes > /dev/null
python3 - "$test_home/.config/mrcall-ai-kit/installed.tsv" <<'CHECK'
from pathlib import Path
import sys
p=Path(sys.argv[1])
p.write_text(''.join('\t'.join(line.split('\t')[:5])+'\n' for line in p.read_text().splitlines()))
CHECK
printf 'Foreign older copy.\n' >> "$test_home/.config/mrcall-ai-kit/AGENTS.block.md"
cp "$test_home/.config/mrcall-ai-kit/AGENTS.block.md" "$TEST_ROOT/legacy-foreign"
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes > /dev/null
cmp "$test_home/.config/mrcall-ai-kit/AGENTS.block.md" "$TEST_ROOT/legacy-foreign"
test ! -e "$test_home/.agents/skills/doc-start"
echo 'copy removal without checkout and five-field log compatibility: PASS'
