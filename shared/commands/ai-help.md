---
description: List everything mrcall-ai-kit actually has installed right now — commands, skills, and agents, with their descriptions — instead of a static list that goes stale.
allowed-tools: Bash(ls *) Bash(cat *) Bash(test *) Bash(grep *) Read Glob
---

Report what is installed, by looking at the filesystem — never from memory of
what the kit "usually" ships, since that drifts the moment a piece is added or
removed. Read the `description` (and, for agents, `model`) out of each file's
YAML frontmatter; do not paraphrase it.

## Detect which environments are present

!`test -d ~/.claude && echo "Claude Code: ~/.claude"`
!`test -d ~/.config/opencode && echo "OpenCode: ~/.config/opencode"`
!`test -d ~/.agents/skills && echo "Codex: ~/.agents/skills"`

Only report on environments that exist. If none do, say the kit does not
appear to be installed and point to `./install.sh` in the mrcall-ai-kit repo.

## For each present environment, enumerate

- **Commands** (`<env>/commands/*.md`, Claude Code and OpenCode only — Codex
  has no commands dir): for each file, read its frontmatter `description`.
- **Skills**: Claude Code and OpenCode at `<env>/skills/*/SKILL.md`; Codex at
  `<env>/*/SKILL.md` — its env root (`~/.agents/skills`) already IS the skills
  directory, with no nested `skills/` subfolder. For each skill directory,
  read its `SKILL.md` frontmatter `description`.
- **Agents** (`<env>/agents/*.md`, Claude Code and OpenCode only): for each
  file, read `description` and `model`.

## Router state (Claude Code only)

!`test -f ~/.config/mrcall-ai-kit/router.on && echo "router flag: ON" || echo "router flag: off"`
!`test -f ~/.claude/settings.json && grep -q router-hook ~/.claude/settings.json 2>/dev/null && echo "router hook: registered" || echo "router hook: not registered"`

Report both lines as-is; if the router command/agents aren't installed at
all, skip this section rather than explaining what the router is.

## Output shape

One compact table per category (Commands / Skills / Agents), each row
`name — description`, grouped by environment when more than one is present.
Close with the router state lines (if applicable) and, only if this session
is running inside the mrcall-ai-kit repo itself, a pointer to
`docs/documentation-harness.md` for the full contract — otherwise omit that
line rather than guessing a path.

Keep it a reference listing, not a tutorial: no walkthroughs of how to use
each thing, one line per item is enough. Someone asking "what do I have" wants
the inventory, not the manual.
