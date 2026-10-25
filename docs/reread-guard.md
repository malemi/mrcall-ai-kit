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

## Mandate completion

Doc-harness removes owned [automatic-av registrations](runtime-completion.md).
Automatic report selection and stance continuation are disabled; manual av is
unchanged. This retirement is separate from optional sc, the six-item clarity
checklist and the repository completion-evidence CLI.

Before yielding, generated agents assess their whole bounded assignment and
perform a useful authorized next action when one remains feasible within limits.
They distinguish verified completion from an honest report of unfinished work.
Questions and brief/review-only requests retain their limited scope. Missing
indispensable input or authority, a blocker leaving no independent useful work,
an explicit pause, or an actual resource/runtime limit permits an incomplete
handoff with remaining obligations. Existing plans/handoffs carry pending state;
the instruction itself creates no task database or per-answer reviewer.
Automatic av no longer supplies a separate native continuation.

The source is `shared/roles/block-mandate-completion.md`. It is composed into the
Codex global kit block and generated final-report procedures. Codex doc-harness
installation places the lead instruction in `~/.codex/AGENTS.md`; it applies even
without a repository profile. OpenCode generated leads receive it inline. Claude
kit workers receive it through their preloaded role skill; ordinary Claude leads
are not covered by this new route. The optional operator-only `sc` procedure
still uses the six-item editable checklist; its activation rules are unchanged.

Update an existing Codex install with `./install.sh --environment codex
--features doc-harness --mode copy --on-exist overwrite --yes`, then restart
sessions. Choose symlink mode instead when that is the intended installation.
The global AGENTS block and physical Codex role profiles require installer refresh
even in symlink mode. Source-linked OpenCode agents and the Claude role skill
reflect checkout edits without reinstalling; new sessions/workers may load those
changes. `skip` preserves an existing block. Installation preserves
operator-owned surrounding text; no repository migration is needed. Existing sessions require a restart to receive the refreshed global block.

Native Codex CLI 0.163.0, isolated copy install, ephemeral workspace-write turns,
and the operator's configured model/reasoning produced nine passing cases:
multi-step completion, repair after a failed real check, supplied active-mandate
status, supplied-plan resumption, missing publish authorization with independent
preparation, read-only question, brief-only artifact, pause, and a one-command cap.
Positive cases contain actual generated outputs and successful CLI checks; the
repair records a failure followed by success. Negative cases preserve forbidden
side-effect boundaries. Original logs and hash-bound reassessments are retained
under `/tmp/mrcall-ai-kit/mandate-completion/native/` on the acceptance host.

The opt-in runner is `tests/mandate_completion_native.py`: `--self-check` runs free
fixture/limit checks; `--run ABS_EVIDENCE_DIR` buys a native matrix; `--verify
ABS_EVIDENCE_DIR` checks retained evidence without model calls. `--reassess` checks
a complete matrix with the current assessor, preserving original records. The measured matrix contains nine conversations, 207.472 seconds in total, with
no native retries.
Reported cumulative input/cached-input/output/reasoning usage was
713968/565888/5499/797 tokens; review-worker usage is separate. There is no
old-rule control group or measured improvement rate.

The runner stops on first failure, counts attempts in its evidence directory,
refuses more than ten conversations there, and kills its native process group
at 180 seconds, oversized output, or an observed ninth tool item. These are
runner limits, not a general host interception mechanism. Reusing another evidence
directory does not authorize more spending. The monitor counts shell commands, file changes and external/delegated tool
items. Retained evidence can also be checked against that allowance without
calling a model.

These samples do not establish interactive behavior, long-session reliability,
actual compaction persistence, lifecycle compliance, or native Claude/OpenCode
adherence. Status/resumption fixtures supply single-turn context. The unprofiled brief-only sample is not proof of startup enforcement. Instruction following can
still fail. That historical instruction matrix does not test the separate
automatic av adapter.

## Re-read runtime measurements

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
