#!/usr/bin/env bash
# Inventory of what mrcall-ai-kit has installed, read from disk and emitted
# ready to print. It lives in its own file rather than inline in the command
# because Claude Code delimits an injected shell block with backticks, and a
# script that formats a model column needs backticks of its own.
#
# Argument: empty for the runtime this is running in, `all` for every runtime.
set -uo pipefail

one_line() { # first sentence of the frontmatter description, capped
  awk -F'description: ' '/^description:/{print $2; exit}' "$1" \
    | sed 's/[.!?] .*/./; s/^\(.\{110\}\).*/\1…/'
}

model_of() { awk -F'model: ' '/^model:/{print $2; exit}' "$1"; }

here="Codex"
[ -n "${CLAUDECODE:-}" ] && here="Claude Code"
[ -n "${OPENCODE:-}${OPENCODE_BIN_PATH:-}" ] && here="OpenCode"
[ "${1:-}" = all ] && here=all

show() { [ "$here" = all ] || [ "$here" = "$1" ]; }
head2() { printf '\n**%s**\n\n| name | what it is |\n|---|---|\n' "$1"; }

for entry in "Claude Code|$HOME/.claude" "OpenCode|$HOME/.config/opencode"; do
  name=${entry%%|*}; root=${entry#*|}
  show "$name" || continue

  if compgen -G "$root/commands/*.md" >/dev/null; then
    head2 "$name — commands (type /<name>)"
    for f in "$root"/commands/*.md; do
      printf '| %s | %s |\n' "$(basename "$f" .md)" "$(one_line "$f")"
    done
  fi

  if compgen -G "$root/skills/*/SKILL.md" >/dev/null; then
    head2 "$name — skills (model-invoked)"
    for f in "$root"/skills/*/SKILL.md; do
      printf '| %s | %s |\n' "$(basename "$(dirname "$f")")" "$(one_line "$f")"
    done
  fi

  if compgen -G "$root/agents/*.md" >/dev/null; then
    printf '\n**%s — agents**\n\n| name | model | what it is |\n|---|---|---|\n' "$name"
    for f in "$root"/agents/*.md; do
      printf '| %s | `%s` | %s |\n' \
        "$(basename "$f" .md)" "$(model_of "$f")" "$(one_line "$f")"
    done
  fi
done

if show Codex && compgen -G "$HOME/.agents/skills/*/SKILL.md" >/dev/null; then
  head2 "Codex — skills (ask by name, or by the trigger in its description)"
  for f in "$HOME"/.agents/skills/*/SKILL.md; do
    printf '| %s | %s |\n' "$(basename "$(dirname "$f")")" "$(one_line "$f")"
  done
fi

# Hook-backed features have a state the file listing cannot show: a command can
# be installed while its hook is dormant, or registered and switched off. Each
# line below is one such feature — flag first, then whether Claude Code actually
# calls it, because a flag with no registration does nothing at all.
hook_state() { # $1=label $2=flag file $3=script name to find in settings.json
  printf '\n%s: ' "$1"
  [ -f "$HOME/.config/mrcall-ai-kit/$2" ] && printf 'flag ON' || printf 'flag off'
  grep -q "$3" "$HOME/.claude/settings.json" 2>/dev/null \
    && printf ', hook registered\n' || printf ', hook not registered\n'
}
hook_state router router.on router-hook
if [ -f "$HOME/.config/mrcall-ai-kit/reread-hook.py" ]; then
  # The re-read guard has two flags: one armed for a single answer, one that
  # stays. Report the persistent one — a one-shot is spent before anyone reads
  # this, so printing it would only ever be noise.
  hook_state "re-read guard" reread.on reread-hook
fi

[ "$here" = all ] || printf '\nShowing %s only. `/ai-help all` for every runtime.\n' "$here"
