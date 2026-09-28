#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

absent() { [[ ! -e "$1" && ! -L "$1" ]]; }

for mode in copy symlink; do
  for runtime in claude opencode codex all; do
    test_home="$TEST_ROOT/$mode-$runtime"
    mkdir -p "$test_home"
    HOME="$test_home" "$KIT_DIR/install.sh" --environment "$runtime" \
      --features reread --mode "$mode" --on-exist skip --yes >/dev/null

    kit="$test_home/.config/mrcall-ai-kit"
    cc="$test_home/.claude/commands/sc.md"
    hook="$kit/reread-hook.py"
    oc="$test_home/.config/opencode/commands/sc.md"
    cx="$test_home/.agents/skills/sc"
    core="$kit/sc-core.md"
    checklist="$kit/reread-checklist.md"

    test -f "$checklist"
    cmp "$KIT_DIR/shared/roles/reread-checklist.md" "$checklist"

    if [[ "$runtime" == claude || "$runtime" == all ]]; then
      test -f "$cc"; test -f "$hook"
      cmp "$KIT_DIR/claude/commands/sc.md" "$cc"
    else
      absent "$cc"; absent "$hook"
    fi
    if [[ "$runtime" == opencode || "$runtime" == all ]]; then
      test -f "$oc"
      cmp "$KIT_DIR/opencode/commands/sc.md" "$oc"
    else
      absent "$oc"
    fi
    if [[ "$runtime" == codex || "$runtime" == all ]]; then
      test -f "$cx/SKILL.md"
      cmp "$KIT_DIR/codex/skills/sc/SKILL.md" "$cx/SKILL.md"
    else
      absent "$cx"
    fi
    if [[ "$runtime" == opencode || "$runtime" == codex || "$runtime" == all ]]; then
      test -f "$core"
      cmp "$KIT_DIR/shared/shortcuts/sc-core.md" "$core"
    else
      absent "$core"
    fi

    if [[ "$mode" == symlink ]]; then
      test -L "$checklist"
      [[ "$runtime" == claude ]] || test -L "$core"
      [[ "$runtime" != codex && "$runtime" != all ]] || test -L "$cx"
    else
      test ! -L "$checklist"
      [[ "$runtime" == claude ]] || test ! -L "$core"
      [[ "$runtime" != codex && "$runtime" != all ]] || { test -d "$cx"; test ! -L "$cx"; }
    fi

    manifest="$kit/installed.tsv"
    python3 - "$manifest" <<'PY'
from collections import Counter
from pathlib import Path
import sys

destinations = [line.split("\t")[2] for line in Path(sys.argv[1]).read_text().splitlines()]
duplicates = {path: count for path, count in Counter(destinations).items() if count != 1}
assert not duplicates, duplicates
PY

    HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
    absent "$cc"; absent "$hook"; absent "$oc"; absent "$cx"
    absent "$core"; absent "$checklist"
  done
done
echo "reread copy/symlink install and manifest uninstall per runtime: PASS"

# The doc-harness directory sweeps must not install sc on their own or add a
# second copy when both features are selected under the backup policy.
doc_only="$TEST_ROOT/doc-only"
mkdir -p "$doc_only"
HOME="$doc_only" "$KIT_DIR/install.sh" --environment all \
  --features doc-harness --mode symlink --on-exist skip --yes >/dev/null
absent "$doc_only/.claude/commands/sc.md"
absent "$doc_only/.config/opencode/commands/sc.md"
absent "$doc_only/.agents/skills/sc"
absent "$doc_only/.config/mrcall-ai-kit/sc-core.md"
absent "$doc_only/.config/mrcall-ai-kit/reread-checklist.md"

combined="$TEST_ROOT/combined"
mkdir -p "$combined"
HOME="$combined" "$KIT_DIR/install.sh" --environment all \
  --features doc-harness,reread --mode symlink --on-exist backup --yes >/dev/null
test -f "$combined/.claude/commands/sc.md"
test -f "$combined/.config/opencode/commands/sc.md"
test -f "$combined/.agents/skills/sc/SKILL.md"
test -f "$combined/.config/mrcall-ai-kit/sc-core.md"
test -f "$combined/.config/mrcall-ai-kit/reread-checklist.md"
python3 - "$combined/.config/mrcall-ai-kit/installed.tsv" <<'PY'
from collections import Counter
from pathlib import Path
import sys

destinations = [line.split("\t")[2] for line in Path(sys.argv[1]).read_text().splitlines()]
duplicates = {path: count for path, count in Counter(destinations).items() if count != 1}
assert not duplicates, duplicates
PY
for file in \
  "$combined/.claude/commands/sc.md.bak" \
  "$combined/.config/opencode/commands/sc.md.bak" \
  "$combined/.config/mrcall-ai-kit/sc-core.md.bak" \
  "$combined/.config/mrcall-ai-kit/reread-checklist.md.bak"; do
  absent "$file"
done
absent "$combined/.config/mrcall-ai-kit/backups/.agents/skills/sc"
HOME="$combined" "$KIT_DIR/uninstall.sh" --yes >/dev/null
absent "$combined/.claude/commands/sc.md"
absent "$combined/.config/opencode/commands/sc.md"
absent "$combined/.agents/skills/sc"
absent "$combined/.config/mrcall-ai-kit/sc-core.md"
absent "$combined/.config/mrcall-ai-kit/reread-checklist.md"
echo "reread stays inside its feature gate and creates no duplicate destination: PASS"
