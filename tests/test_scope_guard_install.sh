#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

install_scope() {
  HOME="$1" "$KIT_DIR/install.sh" --environment "$2" --features scope-guard \
    --mode "$3" --on-exist skip --yes "${@:4}"
}

# Copy and symlink installs place complete, dormant kit-owned artifacts without
# touching any runtime hook registry. --yes is intentionally not activation.
for mode in copy symlink; do
  test_home="$TEST_ROOT/dormant-$mode"
  mkdir -p "$test_home"
  install_scope "$test_home" all "$mode" >/dev/null
  test -f "$test_home/.config/mrcall-ai-kit/scope-guard/scope_guard.py"
  test -f "$test_home/.config/mrcall-ai-kit/scope-guard/scope_guard_register.py"
  test -f "$test_home/.config/mrcall-ai-kit/scope-guard/claude/scope-guard.py"
  test -f "$test_home/.config/mrcall-ai-kit/scope-guard/codex/scope-guard.py"
  test -f "$test_home/.config/mrcall-ai-kit/scope-guard/opencode/scope-guard.ts"
  test -f "$test_home/.claude/commands/scope-guard.md"
  test -f "$test_home/.agents/skills/scope-guard/SKILL.md"
  test -f "$test_home/.config/opencode/commands/scope-guard.md"
  if [[ "$mode" == symlink ]]; then
    test -L "$test_home/.config/mrcall-ai-kit/scope-guard/scope_guard.py"
  else
    test ! -L "$test_home/.config/mrcall-ai-kit/scope-guard/scope_guard.py"
  fi
  test ! -e "$test_home/.claude/settings.json"
  test ! -e "$test_home/.codex/hooks.json"
  test ! -e "$test_home/.config/opencode/plugins/mrcall-scope-guard.ts"
done
echo "scope guard copy/symlink dormant install: PASS"

# A real TTY install asks the exact question once per selected runtime and the
# empty answer defaults to no.
test_home="$TEST_ROOT/interactive-default"
mkdir -p "$test_home"
out="$(printf '\n\n\n' | script -qfec "HOME='$test_home' '$KIT_DIR/install.sh' --environment all --features scope-guard --mode copy --on-exist skip --yes" /dev/null)"
for runtime in claude codex opencode; do
  [[ "$out" == *"Activate scope guard for $runtime now (it adds a hook)?"* ]]
done
test ! -e "$test_home/.claude/settings.json"
test ! -e "$test_home/.codex/hooks.json"
test ! -e "$test_home/.config/opencode/plugins/mrcall-scope-guard.ts"
echo "scope guard interactive prompt and default-no: PASS"

test_home="$TEST_ROOT/dry-run"
mkdir -p "$test_home"
out="$(install_scope "$test_home" claude copy --activate-scope-guard claude --dry-run)"
[[ "$out" == *"activate Claude scope guard -> $test_home/.claude/settings.json"* ]]
test ! -e "$test_home/.config/mrcall-ai-kit"
test ! -e "$test_home/.claude/settings.json"
echo "scope guard dry-run previews activation without writes: PASS"

# An interactive yes and the explicit non-interactive flag activate through the
# same helper. Merely passing --yes above did not.
test_home="$TEST_ROOT/interactive-yes"
mkdir -p "$test_home"
printf 'y\n' | script -qfec "HOME='$test_home' '$KIT_DIR/install.sh' --environment claude --features scope-guard --mode copy --on-exist skip --yes" /dev/null >/dev/null
grep -q 'mrcall-ai-kit/scope-guard/claude/scope-guard.py' "$test_home/.claude/settings.json"

test_home="$TEST_ROOT/active"
mkdir -p "$test_home/.claude" "$test_home/.codex" "$test_home/.config/opencode/plugins"
printf '%s\n' '{"foreign":"keep","hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"foreign-claude"}]}]}}' > "$test_home/.claude/settings.json"
printf '%s\n' '{"foreign":"keep","hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"foreign-codex"}]}]}}' > "$test_home/.codex/hooks.json"
printf 'foreign plugin\n' > "$test_home/.config/opencode/plugins/foreign.ts"
install_scope "$test_home" all copy --activate-scope-guard all >/dev/null
grep -q 'foreign-claude' "$test_home/.claude/settings.json"
grep -q 'foreign-codex' "$test_home/.codex/hooks.json"
grep -q 'scope-guard/claude/scope-guard.py' "$test_home/.claude/settings.json"
grep -q 'scope-guard/codex/scope-guard.py' "$test_home/.codex/hooks.json"
test -L "$test_home/.config/opencode/plugins/mrcall-scope-guard.ts"
test "$(cat "$test_home/.config/opencode/plugins/foreign.ts")" = "foreign plugin"
echo "scope guard explicit activation preserves foreign registrations: PASS"

register="$test_home/.config/mrcall-ai-kit/scope-guard/scope_guard_register.py"
HOME="$test_home" python3 "$register" claude off >/dev/null
status="$(HOME="$test_home" python3 "$register" claude status)"
[[ "$status" == *"installed, dormant"* ]]
grep -q 'foreign-claude' "$test_home/.claude/settings.json"
! grep -q 'scope-guard/claude' "$test_home/.claude/settings.json"
HOME="$test_home" python3 "$register" claude on >/dev/null
status="$(HOME="$test_home" python3 "$register" claude status)"
[[ "$status" == *"enabled"* ]]
echo "scope guard on/off/status cycle: PASS"

# Repeated registration contains one owned group per event and leaves the
# foreign configuration intact.
HOME="$test_home" python3 "$register" claude on >/dev/null
HOME="$test_home" python3 "$register" codex on >/dev/null
HOME="$test_home" python3 - "$test_home" <<'PY'
import json, pathlib, sys
home = pathlib.Path(sys.argv[1])
for runtime, path in (("claude", home / ".claude/settings.json"), ("codex", home / ".codex/hooks.json")):
    data = json.loads(path.read_text())
    groups = [g for values in data["hooks"].values() for g in values]
    owned = [g for g in groups if any("scope-guard" in h.get("command", "") for h in g.get("hooks", []))]
    assert len(owned) == (3 if runtime == "claude" else 1), owned
PY
echo "scope guard registration idempotence: PASS"

# Uninstall unregisters only owned entries/plugins before removing artifacts.
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
grep -q 'foreign-claude' "$test_home/.claude/settings.json"
grep -q 'foreign-codex' "$test_home/.codex/hooks.json"
! grep -q 'mrcall-ai-kit/scope-guard' "$test_home/.claude/settings.json"
! grep -q 'mrcall-ai-kit/scope-guard' "$test_home/.codex/hooks.json"
test -f "$test_home/.config/opencode/plugins/foreign.ts"
test ! -e "$test_home/.config/opencode/plugins/mrcall-scope-guard.ts"
test ! -e "$test_home/.config/mrcall-ai-kit/scope-guard/scope_guard_register.py"
echo "scope guard uninstall preserves foreign registrations: PASS"
