---
description: List what mrcall-ai-kit has installed for the runtime you are in right now — commands, skills and agents, read from disk. Pass `all` to include the other runtimes.
allowed-tools: Bash(bash *)
---

Print the block below verbatim and stop. Do not re-read any file, do not
re-describe an entry, do not add a summary, a recommendation, or a closing line.
The listing is already formatted; relaying it is the whole job, and anything you
add is a description of the inventory rather than the inventory.

Argument: `$ARGUMENTS` — empty for this runtime only, `all` for every runtime
installed on this machine.

!`bash -s -- "$ARGUMENTS" <<'INV'
d(){ awk -F'description: ' '/^description:/{print $2; exit}' "$1" | sed 's/[.!?] .*/./; s/^\(.\{110\}\).*/\1…/'; }
here="Codex"; [ -n "${CLAUDECODE:-}" ] && here="Claude Code"; [ -n "${OPENCODE:-}${OPENCODE_BIN_PATH:-}" ] && here="OpenCode"
[ "$1" = all ] && here=all
show(){ [ "$here" = all ] || [ "$here" = "$1" ]; }
tbl(){ printf '\n**%s**\n\n| name | what it is |\n|---|---|\n' "$1"; }
for e in "Claude Code|$HOME/.claude" "OpenCode|$HOME/.config/opencode"; do
  n=${e%%|*}; p=${e#*|}; show "$n" || continue
  if compgen -G "$p/commands/*.md" >/dev/null; then tbl "$n — commands (type /<name>)"
    for f in "$p"/commands/*.md; do printf '| %s | %s |\n' "$(basename "$f" .md)" "$(d "$f")"; done; fi
  if compgen -G "$p/skills/*/SKILL.md" >/dev/null; then tbl "$n — skills (model-invoked)"
    for f in "$p"/skills/*/SKILL.md; do printf '| %s | %s |\n' "$(basename "$(dirname "$f")")" "$(d "$f")"; done; fi
  if compgen -G "$p/agents/*.md" >/dev/null; then printf '\n**%s — agents**\n\n| name | model | what it is |\n|---|---|---|\n' "$n"
    for f in "$p"/agents/*.md; do printf '| %s | `%s` | %s |\n' "$(basename "$f" .md)" "$(awk -F"model: " "/^model:/{print \$2; exit}" "$f")" "$(d "$f")"; done; fi
done
if show Codex && compgen -G "$HOME/.agents/skills/*/SKILL.md" >/dev/null; then tbl "Codex — skills (ask by name or by the trigger in its description)"
  for f in "$HOME"/.agents/skills/*/SKILL.md; do printf '| %s | %s |\n' "$(basename "$(dirname "$f")")" "$(d "$f")"; done; fi
printf '\nrouter: '; [ -f "$HOME/.config/mrcall-ai-kit/router.on" ] && printf 'flag ON' || printf 'flag off'
grep -q router-hook "$HOME/.claude/settings.json" 2>/dev/null && printf ', hook registered\n' || printf ', hook not registered\n'
[ "$here" = all ] || printf '\nShowing %s only. `/ai-help all` for every runtime.\n' "$here"
INV`

Descriptions are truncated to one line on purpose: this is an index, and an
entry that needs more than a line is asking to be opened, not summarised here.
Where an entry declares its own trigger, that trigger is in its own description
— open the entry rather than restating it here.

If the block above is empty, the kit is not installed for this runtime; point at
`./install.sh` in the mrcall-ai-kit repo and say nothing else.
