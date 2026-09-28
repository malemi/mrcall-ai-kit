# Re-read pass by runtime

The `reread` feature installs one editable checklist at
`~/.config/mrcall-ai-kit/reread-checklist.md`. Its behavior depends on the
runtime. The OpenCode and Codex paths are instructions to the answering model;
they do not intercept a finished answer before delivery.

| Runtime | Entry point and mechanism | Observed status on 2026-09-28 | Limit |
|---|---|---|---|
| Claude Code | `/sc <question>` arms a Stop hook; `on` and `off` manage a persistent flag | Hook script's eight checks pass. The operator reported that the existing `/sc` had worked before this port and waived a repeat live check. Claude Code 2.1.280 stopped before `/sc` with a weekly usage limit, so this trace provides no new client proof. | The hook skips answers shorter than `SC_MIN_CHARS` (500 by default) and fails open on missing checklist or malformed input. |
| OpenCode | `/sc <question>` inserts the installed procedure and checklist into the command prompt, then instructs one in-turn pass | OpenCode 1.18.32, isolated copy install: the default `opencode/big-pickle` answered a short question with the checklist marker; `opencode/gpt-6-sol` read a file in the workspace, counted its three nonempty lines, and included the marker in a 791-character answer. Missing procedure and checklist each produced an install error. Empty argument and four Claude-only modes produced usage/unsupported responses. | The model may ignore the instruction; there is no Stop interception or always-on mode. |
| Codex | `$sc <question>` invokes a skill that reads the installed procedure and checklist, then instructs one in-turn pass | Codex CLI 0.157.1, isolated copy install: a short answer and an 864-character answer about a read workspace file included the checklist marker. Missing files produced install errors. A plain question did not invoke the skill; empty argument and four Claude-only modes produced usage/unsupported responses. | The model may invoke or ignore the skill contrary to its description; there is no Stop interception or always-on mode. |

The live-client check appended a temporary instruction to end the answer with
`REREADQA4821`. The marker was absent from the user question. OpenCode session
exports contained the expanded common procedure and checklist; Codex JSON
events showed reads of both installed files. The long-answer prompts asked the
clients to read a disposable `example.txt` with three nonempty lines; their
tool traces showed that read and their final answers reported three. The
temporary checklist addition was removed after the checks.

The isolated clients used `HOME=/tmp/mrcall-reread-qa.pxhCO8tZ`, populated by
`install.sh --environment all --features reread --mode copy`. The command
file was under `.config/opencode/commands/sc.md`, the Codex skill under
`.agents/skills/sc/SKILL.md`, and both shared files under
`.config/mrcall-ai-kit/` in that HOME. OpenCode was invoked with
`opencode run --command sc ... --format json`; Codex was invoked with
`codex exec --ephemeral --ignore-user-config --sandbox read-only ... --json`.
These observations show that the tested clients loaded the entry points and
used the checklist in
those turns. They do not expose an internal draft, establish that a correction
occurred, or guarantee that future answers will follow the instruction.

OpenCode's command uses shell expansion to read the two fixed installed paths
before the model sees the prompt. The question is never inserted into a shell
command. This avoids a tool permission request for files outside the project
directory, which blocked a live read-tool attempt during testing. Commands
from untrusted sources should not be installed because OpenCode executes their
shell blocks before its tool permission flow.

Claude Code 2.1.280 returned a weekly usage-limit message before it could run
the command. The shell hook test proves local payload handling, not an
installed-client interaction. On 2026-09-28 the operator said the existing
Claude `/sc` worked and waived a repeat live check for this port. This is an
acceptance decision, not a new observation of Claude client behavior.
