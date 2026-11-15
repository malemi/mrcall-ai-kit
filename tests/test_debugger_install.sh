#!/usr/bin/env bash
set -euo pipefail
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" --environment all --features doc-harness \
    --mode "$mode" --on-exist skip --yes > /dev/null
  cmp "$test_home/.codex/agents/debugger.toml" "$KIT_DIR/codex/agents/debugger.toml"
  test ! -L "$test_home/.codex/agents/debugger.toml"
  cmp "$test_home/.claude/agents/debugger.md" "$KIT_DIR/claude/agents/medium/debugger.md"
  cmp "$test_home/.config/opencode/agents/debugger.md" "$KIT_DIR/opencode/agents/medium/debugger.md"
  HOME="$test_home" bash "$test_home/.config/mrcall-ai-kit/ai-help.sh" all > "$TEST_ROOT/help"
  grep -q '| debugger | inherits session model |' "$TEST_ROOT/help"
  HOME="$test_home" python3 "$test_home/.config/mrcall-ai-kit/ai-budget.py" low > /dev/null
  cmp "$test_home/.claude/agents/debugger.md" "$KIT_DIR/claude/agents/low/debugger.md"
  cmp "$test_home/.config/opencode/agents/debugger.md" "$KIT_DIR/opencode/agents/low/debugger.md"
  HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes > /dev/null
  test ! -e "$test_home/.codex/agents/debugger.toml"
  test ! -e "$test_home/.claude/agents/debugger.md"
  test ! -e "$test_home/.config/opencode/agents/debugger.md"
done

python3 - "$KIT_DIR" <<'PY'
from pathlib import Path
import json, sys, tomllib
root=Path(sys.argv[1])
profile=tomllib.loads((root/'codex/agents/debugger.toml').read_text())
assert profile['sandbox_mode']=='read-only' and 'model' not in profile
for runtime in ('claude','opencode'):
    for budget in ('low','medium','high'):
        path=root/runtime/'agents'/budget/'debugger.md'
        frontmatter=path.read_text().split('---',2)[1]
        fields=dict(line.split(': ',1) for line in frontmatter.splitlines() if ': ' in line)
        description=json.loads(fields['description'])
        assert isinstance(description,str) and description
        assert fields['model'].strip()
        if runtime=='claude':
            assert 'Edit' not in fields['tools'].split(', ')
        else:
            assert fields['mode']=='subagent' and fields['  edit']=='deny'
requirements=json.loads((root/'shared/roles/requirements.json').read_text())
selection=json.loads((root/'shared/roles/models.json').read_text())
for runtime, spec in requirements['runtimes'].items():
    assert spec['roles']['debugger']==spec['roles']['verify']
    for outcome in selection['runtimes'][runtime].values():
        assert outcome['roles']['debugger']['model']==outcome['roles']['verify']['model']
print('debugger copy/symlink install, discovery, budget switch, uninstall and model policy: PASS')
PY
