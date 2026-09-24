#!/usr/bin/env bash
# What each installed capability is for, and when to reach for it.
#
# `/ai-help` answers "what do I have"; this answers "what is it for". Different
# questions, so two commands rather than one that does both badly.
#
# It prints only the sections whose proof artifact is on disk, so a reader is
# never taught a feature they do not have. The prose lives in shared/tutorial.md,
# one section per CAPABILITY — a command ships three times for three runtimes,
# and explaining it three times is how the rest of this kit drifted.
#
# Argument: empty for the runtime this is running in, `all` for every runtime,
# or a capability name to print one section.
set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Installed next to the script by install.sh; in a source checkout it is a
# directory up. Checking both means the command works from either.
for candidate in "$SELF_DIR/tutorial.md" "$SELF_DIR/../tutorial.md"; do
  [ -f "$candidate" ] && TUTORIAL="$candidate" && break
done
if [ -z "${TUTORIAL:-}" ]; then
  echo "tutorial source not found — reinstall with ./install.sh --features doc-harness" >&2
  exit 1
fi

WANT="${1:-}"

here="Codex"
[ -n "${CLAUDECODE:-}" ] && here="Claude Code"
[ -n "${OPENCODE:-}${OPENCODE_BIN_PATH:-}" ] && here="OpenCode"

# Where an installed artifact would be, per runtime. A capability counts as
# present when its proof path exists under any root we are showing.
roots() {
  case "$here" in
    "Claude Code") printf '%s\n' "$HOME/.claude" ;;
    OpenCode)      printf '%s\n' "$HOME/.config/opencode" ;;
    Codex)         printf '%s\n' "$HOME/.agents" ;;
  esac
  [ "$WANT" = all ] && printf '%s\n%s\n%s\n' \
    "$HOME/.claude" "$HOME/.config/opencode" "$HOME/.agents"
}

have() { # $1 = proof path relative to a runtime root
  local proof="$1" root
  while read -r root; do
    [ -n "$root" ] || continue
    [ -e "$root/$proof" ] && return 0
    # Codex ships commands as skills: commands/x.md -> skills/x/SKILL.md
    case "$proof" in
      commands/*.md)
        local name="${proof#commands/}"; name="${name%.md}"
        [ -e "$root/skills/$name/SKILL.md" ] && return 0 ;;
    esac
  done < <(roots)
  return 1
}

shown=0
while IFS= read -r line; do
  case "$line" in
    "<!-- capability: "*)
      cap="${line#<!-- capability: }"; cap="${cap%% *}"
      proof="${line##*proof: }"; proof="${proof%% *}"
      printing=0
      if [ -n "$WANT" ] && [ "$WANT" != all ]; then
        [ "$WANT" = "$cap" ] && printing=1
      elif have "$proof"; then
        printing=1
      fi
      [ "$printing" = 1 ] && shown=$((shown + 1))
      continue ;;
    "<!--"*|*"-->") continue ;;
  esac
  [ "${printing:-0}" = 1 ] && printf '%s\n' "$line"
done < "$TUTORIAL"

if [ "$shown" -eq 0 ]; then
  if [ -n "$WANT" ] && [ "$WANT" != all ]; then
    echo "No section named '$WANT'. Run /ai-tutorial with no argument for what you have."
  else
    echo "Nothing from this kit is installed for $here."
  fi
  exit 0
fi

[ "$WANT" = all ] || printf '\n---\nShowing what is installed for %s. `/ai-tutorial all` for every runtime, `/ai-help` for the bare inventory.\n' "$here"
