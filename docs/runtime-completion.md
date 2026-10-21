# Codex runtime completion check

Codex doc-harness installation registers owned `UserPromptSubmit`, `Stop` and
`SessionEnd` commands in the selected `CODEX_HOME/hooks.json` (default
`~/.codex/hooks.json`). The executable is
`~/.config/mrcall-ai-kit/completion-check/completion_check.py`. Existing hook
entries and operator configuration are preserved. No repository protocol change
or engine modification is required.

## Activation and status

Update with `./install.sh --environment codex --features doc-harness --mode copy
--on-exist overwrite --yes` (or choose symlink mode). This changes the native hook
definition. Review and approve that definition through Codex `/hooks`; installation
and registration alone do not establish trust or execution. The installer never
writes native trust storage or restarts running sessions. An existing session's
reload/approval must be established in that client before claiming protection.

```bash
python3 ~/.config/mrcall-ai-kit/completion-check/completion_check.py status
```

Status reports file presence, registered events, unknown native trust, and the
last observed terminal audit with its timestamp and session/turn identity.
An old observation does not establish approval of the current definition.
`off` removes only this adapter's entries, `on` restores them, and the manifest
uninstaller removes unchanged owned files and registrations. Foreign files,
modified installed copies and unrelated hooks remain untouched.

## What executes

A normal end of turn is not a declaration that work is complete. Unbound questions,
clarifications and status answers require no review, continuation or repeated
answer. Tracking an open task alone also does not arm review. Admission precedes
answer validation: these unarmed callbacks also return quietly when the final
answer is absent, null, non-string or empty. An exempt `$nr` callback without a
string answer creates no successful audit. Armed non-exempt callbacks still
refuse an absent or non-string final answer.

Review is required only after an explicit `bind --delivery` for the exact current
session/turn, or inside an explicit checked-exec invocation. Every supported
main-session `Stop` then invokes the validator even when the model ignores the
instructions. A declared delivery without a current review is blocked with a
concrete review command and request nonce. The agent must assess the
whole open assignment, earlier requests and later corrections, acceptance,
actual evidence and remaining obligations. Useful authorized work remains work
to do; a progress question does not cancel it. Questions, briefs and reviews keep
their requested scope.

The review command accepts JSON on stdin or through `--input FILE`:

```json
{
  "assignment": "Answer the operator's bounded question.",
  "acceptance": ["The requested answer is supplied."],
  "evidence": [],
  "remaining": [],
  "decision": "complete",
  "rationale": "The answer covers the requested question.",
  "answer": "The exact intended final response."
}
```

Use the exact `review --request PATH` command returned by the hook. The agent
supplies its actual facts, not these example judgments. Review identity binds a
random nonce, session, turn, invocation, workspace and intended answer digest;
line endings and outer whitespace are normalized. Requests expire after ten
minutes, and a consumed receipt cannot be reused. Changed answers require a fresh
review. `stop_hook_active` never grants an automatic pass.

`continue` requires remaining obligations and refuses conclusion. `complete`
requires an empty remaining list. `limited` requires remaining obligations, a
rationale and `stop_condition` of `pause`, `cancel`, `input`, `authority`,
`external` or `resource`. The literal operator command `$nr` at the start of a
prompt has a turn-bound exemption, captured by `UserPromptSubmit`; the adapter
does not classify ordinary prose or infer a task from recent repository work.
An invocation of the skill by name without that literal command is not a native
exemption. Operator interruption remains a host action outside normal Stop.

At most two automatic continuations are allowed. A third unresolved attempt
records failure and returns `continue:false` with an explicit failed-completion
message. This bounds check-induced retries, not the duration or spending of work
the agent performs between terminal attempts. The hook can run after a draft is
already visible; it cannot retract that draft. Semantic judgments and legitimate
stop reasons remain model attestations: the adapter proves execution and binding,
not that the model is honest or correct.

## Explicit harness binding

A caller with the actual native identities can declare delivery of one existing
completion task for the current turn:

```bash
python3 ~/.config/mrcall-ai-kit/completion-check/completion_check.py bind \
  --session SESSION --turn TURN --repo /absolute/repository \
  --task TASK --context CURRENT_LEAD_CONTEXT --delivery
```

This host-side administrative command writes owned runtime state outside a normal
workspace sandbox. The review command instead uses a private per-user temporary
handoff, which is writable from the measured workspace-write sandbox. Binding is
explicit for that session/turn; it is never inferred or propagated to another
turn. Omitting `--delivery` merely tracks the task and does not arm review. An open
task does not turn its later clarification into a delivery. A declared
`complete` decision additionally runs installed `doc-check.py
--completion check`; missing, failing or stale evidence refuses completion.
A `limited` outcome preserves outstanding obligations without claiming that gate
passed. Without a delivery declaration or checked exec, work is governed by the agent
instructions and is not independently intercepted. The adapter does not infer
semantic completion or detect an undeclared claim of success. Checked exec without
a task binding validates its review receipt but not the whole repository harness.

State and terminal audits live under `completion-check/runtime/`, in mode-0700
owned directories and mode-0600 files. Pending challenges use
`/tmp/mrcall-completion-<uid>/` and random filenames; unsafe ownership, permissions
or symlinks refuse validation. `SessionEnd` removes only its session's pending
state, retaining terminal audits. Crashed-session challenges expire; terminal
audits remain available for inspection. Same-user direct file mutation is outside
the attestation boundary.

## Strict automation exit status

Native `codex exec` can return zero after a hook terminates at a failure cap, and
untrusted hooks can be skipped entirely. Use the owned wrapper when process
status matters:

```bash
python3 ~/.config/mrcall-ai-kit/completion-check/completion_check.py exec \
  --cd /absolute/repository 'Your task'
```

Selecting the wrapper explicitly requires review for that process. It runs
native exec with JSON events, retains native output and requires a fresh
matching terminal audit for its random run identity, native session, turn,
workspace and final answer. Missing, malformed, stale, foreign, mismatched or
failed audits return nonzero (3 on audit refusal); native process failures retain
their exit code. Accepted `complete`, `limited` and explicit `exempt` outcomes
return zero and emit `completion.result` with the outcome and remaining
obligations. Zero therefore means an accepted terminal outcome, not necessarily
that the entire assignment is complete. Plain native exec is not promoted to
this stricter contract.

## Measured support and limits

Four scoped Codex 0.163.0 native cases exercise plain exec and actual TUI
conversation with one final answer/one Stop and zero review commands or
continuations; checked-exec and explicitly declared bound delivery still refuse
a deliberately omitted review. The scoped runner uses `--scoped --run` or
`--scoped --verify`, at most four processes, with the same 60-second/2 MB limits.
Evidence is retained under `/tmp/mrcall-ai-kit/completion-scope-20261020/native/`.
The original seven-case matrix below describes the earlier blanket adapter and
its strict validation paths; it does not establish the corrected ordinary-chat
policy.

Codex 0.163.0, isolated copy installations and a deterministic loopback Responses
provider exercise actual native `UserPromptSubmit`, `Stop`, `SessionEnd` and
sandboxed review CLI execution. Seven production cases cover complete, limited,
skipped review, untrusted registration, literal `$nr`, changed reviewed answer
and TUI failure. A deliberately noncompliant response is refused repeatedly;
there is no silent second-pass allowance. The TUI visibly reports the bounded
failure; its observer shutdown is not a successful native process exit.

`tests/runtime_completion_native.py --verify ABS_EVIDENCE_DIR` rechecks retained
results without starting a client or buying inference. `--run ABS_EVIDENCE_DIR
--case NAME` starts one isolated native process, with a seven-process allowance,
60-second timeout and 2 MB output cap. These cases use no model credentials or
paid inference. The earlier four capability probes and the seven production
cases are retained on the acceptance host under
`/tmp/mrcall-ai-kit/completion-stop-20261020/native/`.

This establishes the measured trusted main-session paths only. Ordinary operator
trust/reload, subagents, other clients, long sessions and semantic accuracy remain
unverified. No engine or client-independent mechanism prevents hook disabling,
an untrusted definition, a direct unwrapped exec, or an invented model attestation.
