# Known Issues and Solutions

Recurring problems and their fixes.

## Claude Code does not hot-reload agent files mid-session

**Symptom**: an agent definition newly installed into `~/.claude/agents/`
returns `Agent type '<name>' not found. Available agents: ...` when passed to
the `Agent` tool as `subagent_type`, and the listed agents are exactly those
that existed when the session started.

**Root cause** (verified 2026-08-04, Claude Code 2.1.220): the agent registry
is built at session start and is not re-read when files appear later. The
definition file itself is not at fault.

**Verification**: installing `worker-sonnet` / `worker-opus` mid-session made
them unreachable in that session, while a fresh headless session started
immediately afterwards (`claude -p "list subagent types"`) listed both. Same
files, same paths, different session.

**Solution**: restart the Claude Code session. This is the same behavior
OpenCode has, below.

**Note**: the installer already prints "restart sessions to pick up new
commands/skills/agents" for this reason.

## OpenCode does not hot-reload agent files mid-session

**Symptom**: a new `*.md` created or copied into
`~/.config/opencode/agents/` during an active session returns `Unknown agent
type: <name> is not a valid agent type` when passed to `task()` as a
`subagent_type`.

**Root cause** (verified 2026-07-25): OpenCode loads its agent registry at
session start and does not hot-reload it. The model ID, YAML frontmatter,
permissions, and path are not responsible.

**Verification**: a control agent named `worker-auto-test` used the known-good
`opencode/gpt-5.4-nano` model, identical to the operational `worker-gpt`, and
returned the same error. This isolates registry loading as the cause.

**Solution**: restart OpenCode so the new agent enters the registry. Creating an
agent mid-session cannot make it available to that session.

**Anti-pattern**: do not retry configuration reloads, alternate paths, or
symlink workarounds. A restart is required.
