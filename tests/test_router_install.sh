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
  # The installed file is really this hook, not another router artifact that
  # merely names the flag: MEMORY_NOTE is what only this file carries.
  grep -q 'MEMORY_NOTE' "$hook" || { echo "installed file is not the router hook" >&2; exit 1; }
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
out="$(HOME="$flag_home" printf '{"session_id":"t1","cwd":"/nonexistent-xyz","transcript_path":"/tmp/t.jsonl"}' | HOME="$flag_home" python3 "$KIT_DIR/claude/scripts/router-hook.py"; printf .)"
# The flag is on but no docs/ tree is in reach, so the hook has no path to name
# and prints nothing at all -- not even a blank line, which would reach the model
# as context that says nothing. The standing contract lives in the managed
# CLAUDE.md and in each worker agent's description, not in this output.
# The trailing dot is the sentinel: `$( )` strips trailing newlines, so without
# it a single blank line would be indistinguishable from no output.
[[ "$out" == "." ]] || { echo "expected no output without a docs/ dir, got: $out" >&2; exit 1; }

docs_home="$TEST_ROOT/docs-home"
mkdir -p "$docs_home/.config/mrcall-ai-kit" "$docs_home/repo/docs"
touch "$docs_home/.config/mrcall-ai-kit/router.on"
out="$(HOME="$docs_home" bash -c "printf '{\"session_id\":\"t1\",\"cwd\":\"$docs_home/repo\",\"transcript_path\":\"/tmp/t.jsonl\"}' | python3 '$KIT_DIR/claude/scripts/router-hook.py'")"
[[ "$out" == *"Session memory"* ]] || { echo "expected memory note with a docs/ dir, got: $out" >&2; exit 1; }
[[ "$out" == *"docs/sessions/t1.md"* ]] || { echo "expected the session file path in the memory note, got: $out" >&2; exit 1; }
echo "router-hook.py dormancy + memory note: PASS"

# One routed turn: <home> <payload> -> the memory note the hook prints.
hook_run() { printf '%s' "$2" | HOME="$1" python3 "$KIT_DIR/claude/scripts/router-hook.py"; }

# ── the session path is pinned: a cd mid-session must not move it ──────────
pin_home="$TEST_ROOT/pin-home"
mkdir -p "$pin_home/.config/mrcall-ai-kit" \
         "$pin_home/repo/docs" "$pin_home/repo/sub/docs" "$pin_home/elsewhere/docs"
touch "$pin_home/.config/mrcall-ai-kit/router.on"
# Every later directory has a docs/ tree of its own, so the old cwd-derived rule
# would have named a different file on each of these turns.
for dir in "$pin_home/repo" "$pin_home/repo/sub" "$pin_home/elsewhere"; do
  out="$(hook_run "$pin_home" "{\"session_id\":\"s1\",\"cwd\":\"$dir\",\"transcript_path\":\"/tmp/t.jsonl\"}")"
  [[ "$out" == *"$pin_home/repo/docs/sessions/s1.md"* ]] \
    || { echo "session path moved after a cd to $dir, got: $out" >&2; exit 1; }
done
# Naming a path is the whole job: the hook creates nothing in any repository.
test ! -e "$pin_home/repo/docs/sessions"
test ! -e "$pin_home/repo/sub/docs/sessions"
test ! -e "$pin_home/elsewhere/docs/sessions"
echo "router-hook.py pins the session path across a cd: PASS"

# ── an existing session file wins, and one session never gets two ──────────
guard_home="$TEST_ROOT/guard-home"
mkdir -p "$guard_home/.config/mrcall-ai-kit" \
         "$guard_home/repo/docs/sessions" "$guard_home/repo/sub/docs/sessions"
touch "$guard_home/.config/mrcall-ai-kit/router.on"
# A session already split by the old rule: first routed turn happens deeper than
# the file it has been accumulating, and no pin exists yet.
printf -- '---\nstatus: open\n---\n' > "$guard_home/repo/docs/sessions/s2.md"
out="$(hook_run "$guard_home" "{\"session_id\":\"s2\",\"cwd\":\"$guard_home/repo/sub\",\"transcript_path\":\"/tmp/t.jsonl\"}")"
[[ "$out" == *"$guard_home/repo/docs/sessions/s2.md"* ]] \
  || { echo "expected the existing session file to be adopted, got: $out" >&2; exit 1; }
# Both exist: the stray one a moved path already created is always the deeper one.
printf -- '---\nstatus: open\n---\n' > "$guard_home/repo/docs/sessions/s3.md"
: > "$guard_home/repo/sub/docs/sessions/s3.md"
out="$(hook_run "$guard_home" "{\"session_id\":\"s3\",\"cwd\":\"$guard_home/repo/sub\",\"transcript_path\":\"/tmp/t.jsonl\"}")"
[[ "$out" == *"$guard_home/repo/docs/sessions/s3.md"* ]] \
  || { echo "expected the outermost existing session file, got: $out" >&2; exit 1; }
echo "router-hook.py adopts an existing session file: PASS"

# ── the starting directory survives in the transcript path ─────────────────
tr_home="$TEST_ROOT/tr-home"
mkdir -p "$tr_home/.config/mrcall-ai-kit" "$tr_home/repo/docs" "$tr_home/repo/sub/docs"
touch "$tr_home/.config/mrcall-ai-kit/router.on"
# Claude Code's project directory: the start directory, slashes and dots dashed.
encoded="$tr_home/repo"; encoded="${encoded//\//-}"; encoded="${encoded//./-}"
out="$(hook_run "$tr_home" "{\"session_id\":\"s4\",\"cwd\":\"$tr_home/repo/sub\",\"transcript_path\":\"$tr_home/.claude/projects/$encoded/s4.jsonl\"}")"
[[ "$out" == *"$tr_home/repo/docs/sessions/s4.md"* ]] \
  || { echo "expected the start directory from the transcript path, got: $out" >&2; exit 1; }
echo "router-hook.py recovers the start directory from the transcript: PASS"
