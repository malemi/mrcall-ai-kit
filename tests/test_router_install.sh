#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

# ── router alone (Claude Code only), symlink mode ──────────────────────────
for mode in copy symlink; do
  test_home="$TEST_ROOT/$mode-home"
  mkdir -p "$test_home"
  HOME="$test_home" "$KIT_DIR/install.sh" \
    --environment claude --features router \
    --mode "$mode" --on-exist skip --yes >/dev/null

  hook="$test_home/.config/mrcall-ai-kit/router-hook.py"
  router_cmd="$test_home/.claude/commands/router.md"
  worker="$test_home/.claude/agents/worker-fable.md"
  test -f "$hook"
  test -x "$hook"
  test -f "$router_cmd"
  test -f "$worker"
  if [[ "$mode" == copy ]]; then
    test ! -L "$hook"
  else
    test -L "$hook"
    test -L "$router_cmd"
    test -L "$worker"
  fi
  # doc-harness was not selected: none of its commands should be present.
  test ! -e "$test_home/.claude/commands/doc-start.md"
done
echo "router install (Claude Code alone): PASS"

# ── router is Claude Code-only: dropped when Claude Code isn't selected ────
test_home="$TEST_ROOT/codex-only"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment codex --features router \
  --mode symlink --on-exist skip --yes >/dev/null 2>&1 || true
test ! -e "$test_home/.config/mrcall-ai-kit/router-hook.py"
echo "router feature dropped without Claude Code: PASS"

# ── router + doc-harness together: worker-fable installed exactly once ─────
test_home="$TEST_ROOT/combined"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment claude --features doc-harness,router \
  --mode symlink --on-exist skip --yes >/dev/null
manifest="$test_home/.config/mrcall-ai-kit/installed.tsv"
count=$(grep -c '\.claude/agents/worker-fable\.md' "$manifest")
[[ "$count" -eq 1 ]] || { echo "expected exactly one worker-fable.md manifest entry, got $count" >&2; exit 1; }
test -f "$test_home/.claude/commands/doc-start.md"
test -f "$test_home/.claude/commands/router.md"
echo "router + doc-harness (no duplicate worker-fable): PASS"

# ── uninstall removes exactly the router artifacts ─────────────────────────
test_home="$TEST_ROOT/uninstall"
mkdir -p "$test_home"
HOME="$test_home" "$KIT_DIR/install.sh" \
  --environment claude --features router \
  --mode symlink --on-exist skip --yes >/dev/null
HOME="$test_home" "$KIT_DIR/uninstall.sh" --yes >/dev/null
test ! -e "$test_home/.claude/commands/router.md"
test ! -e "$test_home/.config/mrcall-ai-kit/router-hook.py"
test ! -e "$test_home/.claude/agents/worker-fable.md"
echo "router uninstall: PASS"

# ── the hook itself: dormant without the flag, injects with it ─────────────
dormant_home="$TEST_ROOT/dormant-home"
mkdir -p "$dormant_home"
out="$(HOME="$dormant_home" printf '{}' | HOME="$dormant_home" python3 "$KIT_DIR/claude/scripts/router-hook.py")"
[[ -z "$out" ]] || { echo "expected no output without the flag, got: $out" >&2; exit 1; }

flag_home="$TEST_ROOT/flag-home"
mkdir -p "$flag_home/.config/mrcall-ai-kit"
touch "$flag_home/.config/mrcall-ai-kit/router.on"
out="$(HOME="$flag_home" printf '{"session_id":"t1","cwd":"/nonexistent-xyz","transcript_path":"/tmp/t.jsonl"}' | HOME="$flag_home" python3 "$KIT_DIR/claude/scripts/router-hook.py")"
[[ "$out" == *"Router mode is ON"* ]] || { echo "expected routing directive, got: $out" >&2; exit 1; }
[[ "$out" != *"Session memory"* ]] || { echo "expected no memory note without a docs/ dir, got: $out" >&2; exit 1; }

docs_home="$TEST_ROOT/docs-home"
mkdir -p "$docs_home/.config/mrcall-ai-kit" "$docs_home/repo/docs"
touch "$docs_home/.config/mrcall-ai-kit/router.on"
out="$(HOME="$docs_home" bash -c "printf '{\"session_id\":\"t1\",\"cwd\":\"$docs_home/repo\",\"transcript_path\":\"/tmp/t.jsonl\"}' | python3 '$KIT_DIR/claude/scripts/router-hook.py'")"
[[ "$out" == *"Session memory"* ]] || { echo "expected memory note with a docs/ dir, got: $out" >&2; exit 1; }
[[ "$out" == *"docs/sessions/t1.md"* ]] || { echo "expected the session file path in the directive, got: $out" >&2; exit 1; }
echo "router-hook.py dormancy + injection: PASS"
