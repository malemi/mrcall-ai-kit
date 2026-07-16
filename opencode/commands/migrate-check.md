---
description: Run a quick audit of the current project's Claude Code → OpenCode migration status
allowed-tools: [bash, glob, grep, read]
---

## Project Migration Check

1. Detect project root via `git rev-parse --show-toplevel`
2. Check for `.claude/` directory and list its contents
3. Check for `.opencode/` directory and list its contents
4. Check for `opencode.json` at project root
5. Check for `CLAUDE.md` at project root
6. List agents in `.claude/agents/` and `.opencode/agents/` (if they exist)
7. List commands in `.claude/commands/` and `.opencode/commands/` (if they exist)
8. Check if `opencode-claude-hooks` plugin is active
9. Produce a migration status report

The report format should match what's in the SKILL.md at `~/.config/opencode/skills/migrate-from-cc/SKILL.md` — look at the "Report Format" section for the exact template.
