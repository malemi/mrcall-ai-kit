# mrcall-opencode-kit

Reusable skills, commands, and workers for OpenCode.

A curated collection of OpenCode configuration: skills for migration and orchestration, slash commands, and a full roster of worker agents for multi-model orchestration.

## What's included

### Skills

- **migrate-from-cc** — Detect and migrate Claude Code projects to OpenCode (agents, commands, settings)
- **orchestrator** — Interactive multi-step orchestration with worker delegation and approval gates

### Commands

- `/migrate-check` — Quick audit of migration status (global, works from any directory)
- `/orchestrator` — Launch interactive orchestrator

### Agents

- **build** — Default architect/orchestrator agent
- **plan** — Read-only analysis agent
- **orchestrator** — Interactive planning with user approval
- **reviewer** — Code review and verification
- **15 worker agents** — DeepSeek, Gemini, GLM, GPT, Kimi, Llama, MiMo, Mistral, Nemotron, Qwen, Sonnet

## What's NOT included

- Project-specific agents (e.g. domain specialists) — those stay in your project config
- `opencode.json` — provider config, model defaults (your local config)
- `HACKS.md` — machine-specific workarounds
- `memory.md` — session-specific state

## Install

```bash
git clone https://github.com/malemi/mrcall-opencode-kit.git
cd mrcall-opencode-kit
./install.sh
```

Options:
- `--copy` : copy files instead of symlinking (default: symlink)
- `--force` : overwrite existing files
- `--dry-run` : preview what would be installed

After install, restart OpenCode sessions to pick up the new skills.

## Uninstall

```bash
./uninstall.sh
```

Only removes symlinks pointing to this kit. Your local config files are untouched.

## Skills format

All skills use the standard OpenCode `SKILL.md` format:

```yaml
---
name: skill-name
description: Short description of what the skill does
---
```

Place skills in `~/.config/opencode/skills/<name>/SKILL.md` (global) or `.opencode/skills/<name>/SKILL.md` (project-local).

## License

MIT — use it, fork it, improve it.
