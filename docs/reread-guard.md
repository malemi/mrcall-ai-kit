# Re-read pass by runtime

The `reread` feature installs one editable checklist at
`~/.config/mrcall-ai-kit/reread-checklist.md`. Its behavior depends on the
runtime. The OpenCode and Codex paths are instructions to the answering model;
they do not intercept a finished answer before delivery.

Separately, every kit agent definition includes the six rules from the source
checklist and tells the agent to check its final report. This applies whether
or not the optional `reread` feature is installed. Required report headers and
reviewer verdict placement still govern the opening line. Generated agents
capture the source checklist at build time; editing the optional installed
checklist changes `sc` but does not update those agent definitions. The agent
pass is an instruction, not observable runtime enforcement.

Generated agent profiles have been checked on all three platforms. OpenCode
1.18.32 and Codex 0.158.0 also produced role reports with their required
verdict openings. Claude Code 2.1.280 could not run the agent because of its
weekly usage limit, so Claude client behavior remains unverified. These checks
cannot reveal whether a model privately re-read a draft. The dated
[brief](briefs/2026-09-28-agent-reread-rules.md) and
[plan](execution-plans/2026-09-28-agent-reread-rules.md) record the work trace.

| Runtime | Entry point and mechanism | Observed status on 2026-09-28 | Limit |
|---|---|---|---|
| Claude Code | `/sc <question>` arms a Stop hook; `on` and `off` manage a persistent flag | Hook script's eight checks pass. The operator reported that the existing `/sc` had worked before this port and waived a repeat live check. Claude Code 2.1.280 stopped before `/sc` with a weekly usage limit, so this trace provides no new client proof. | The hook skips answers shorter than `SC_MIN_CHARS` (500 by default) and fails open on missing checklist or malformed input. |
| OpenCode | `/sc <question>` inserts the installed procedure and checklist into the command prompt, then instructs one in-turn pass | OpenCode 1.18.32, isolated copy install: the default `opencode/big-pickle` answered a short question with the checklist marker; `opencode/gpt-6-sol` read a file in the workspace, counted its three nonempty lines, and included the marker in a 791-character answer. Missing procedure and checklist each produced an install error. Empty argument and four Claude-only modes produced usage/unsupported responses. | The model may ignore the instruction; there is no Stop interception or always-on mode. |
| Codex | `$sc <question>` invokes a skill that reads the installed procedure and checklist, then instructs one in-turn pass | Codex CLI 0.157.1, isolated copy install: a short answer and an 864-character answer about a read workspace file included the checklist marker. Missing files produced install errors. A plain question did not invoke the skill; empty argument and four Claude-only modes produced usage/unsupported responses. On 2026-09-28, the operator reported that `$sc` works in the current Codex client after installation; the report supplied no test details. | The model may invoke or ignore the skill contrary to its description; there is no Stop interception or always-on mode. |

OpenCode's command uses shell expansion to read the two fixed installed paths
before the model sees the prompt. The question is never inserted into a shell
command and avoids a read-tool permission request for files outside the project
directory. Commands
from untrusted sources should not be installed because OpenCode executes their
shell blocks before its tool permission flow.
