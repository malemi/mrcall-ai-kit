# Known Issues and Solutions

Recurring problems and their fixes.

## Claude Code re-reads the agent directory between turns

**Behavior** (verified 2026-09-25, Claude Code 2.1.280): an agent file added to
or removed from `~/.claude/agents/` during a session takes effect at that
session's next turn.

**Verification**: a session started with the model-named workers installed.
Mid-session, they were retired and `execute`, `verify` and `reviewer` were
installed. At its next turn, that session delegated to `execute`, and it was
refused `worker-opus` with `Agent type 'worker-opus' not found. Available
agents: ... execute ... reviewer ... verify`.

**Older versions**: Claude Code 2.1.220 (verified 2026-08-04) built the
registry once, at session start. An agent installed mid-session was not found
until the session restarted.

**Not established**: whether an edited agent file, such as one with a changed
`model:`, takes effect mid-session. The measurement above covers files added
and removed only. Until that is measured, restarting the session is the way
to make an edit certain. The installer's "restart sessions" line covers that
case.

**`*.md.bak` is not an agent** (verified 2026-09-25, Claude Code 2.1.280): a
project `.claude/agents/` holding `probe-live.md` and `probe-bak.md.bak` offers
only `probe-live`. The `<file>.bak` that `install.sh --on-exist backup` leaves
in an agent directory does not load.

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

## `opencode run` hangs when stdin is not a terminal

**Symptom**: `opencode run --agent <name> "<message>"` started from a script or
from an agent's shell prints nothing and never returns. Its log
(`~/.local/share/opencode/log/opencode.log`) ends at `message=init`, with no
session created and no model call.

**Root cause** (verified 2026-09-25, opencode 1.17.18): when stdin is not a
terminal, `opencode run` waits to read it, and an open pipe that never closes
keeps it waiting.

**Solution**: give it an empty stdin, `opencode run ... < /dev/null`. The same
command then delegated from `build` to `execute` and returned within seconds.
