# Known Issues and Solutions

Recurring problems and their fixes.

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
