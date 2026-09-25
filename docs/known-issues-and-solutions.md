# Known Issues and Solutions

Recurring problems and their fixes.

## Claude Code re-reads the agent directory between turns

**Behavior** (verified 2026-09-25, Claude Code 2.1.280): an agent file added to
or removed from `~/.claude/agents/` during a session takes effect at that
session's next turn. An agent file edited in a project's `.claude/agents/`,
including a link re-pointed to another file, takes effect at the next
delegation. An edit at user level, which is what a `/ai-budget` switch makes, was
not run itself; it is expected to reach sessions already open the same way,
because the directory is re-read in both places.

**Verification**: a session started with the model-named workers installed.
Mid-session, they were retired and `execute`, `verify` and `reviewer` were
installed. At its next turn, that session delegated to `execute`, and it was
refused `worker-opus` with `Agent type 'worker-opus' not found. Available
agents: ... execute ... reviewer ... verify`.

**Verification of an edit**: one `claude -p` process in stream-json mode, two
turns, each delegating to an agent in the project's `.claude/agents/`. Between
the turns the agent's `model:` was changed from `claude-haiku-4-5` to
`claude-sonnet-5`, and in a second run its symlink was re-pointed from a
`claude-sonnet-5` file to a `claude-haiku-4-5` one, as `/ai-budget` does in
symlink mode. In both runs each subagent ran on the model its file named at the
time of the call, as the subagent's own transcript records (`message.model`).
An agent added to the project between the turns was callable at the second.

**Older versions**: Claude Code 2.1.220 (verified 2026-08-04) built the
registry once, at session start. An agent installed mid-session was not found
until the session restarted.

**`*.md.bak` is not an agent** (verified 2026-09-25, Claude Code 2.1.280): a
project `.claude/agents/` holding `probe-live.md` and `probe-bak.md.bak` offers
only `probe-live`. The `<file>.bak` that `install.sh --on-exist backup` leaves
in an agent directory does not load.

## OpenCode reads its agent files once, when its process starts

**Symptom**: a new `*.md` created or copied into
`~/.config/opencode/agents/` during an active session returns `Unknown agent
type: <name> is not a valid agent type` when passed to `task()` as a
`subagent_type`.

**Root cause** (verified 2026-07-25, and on opencode 1.17.18 on 2026-09-25):
OpenCode loads its agent registry when its process starts and does not re-read
it. A session created later in the same process gets the same registry. The
model ID, YAML frontmatter, permissions, and path are not responsible.

**Verification**: a control agent named `worker-auto-test` used the known-good
`opencode/gpt-5.4-nano` model, identical to the operational `worker-gpt`, and
returned the same error. This isolates registry loading as the cause.

**An edited agent is not re-read either** (verified 2026-09-25, opencode
1.17.18): a headless `opencode serve` in a temporary home kept the model it had
loaded for an agent after the file's `model:` changed. `GET /agent` showed the
old model, also for a session created after the edit, and a prompt through the
server (`opencode run --attach`), which opens a new session, resolved the old
model id. A fresh `opencode run` resolved the new one. The ids were ones no
provider has, so the check called no model. The TUI was not driven. So a
`/ai-budget` switch reaches an OpenCode started after it; one already running
keeps its old models, in new sessions too, until it is restarted.

**Solution**: restart OpenCode so the new agent, or the agent's new model,
enters the registry. Creating or editing an agent while OpenCode runs cannot
change that process, whichever session it is in.

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
